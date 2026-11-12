"""Once-only execution of business commands.

Every stock-changing request carries a retry key. The first request with a key
runs the command and stores its result in the same database transaction. A
repeat with the same key and the same details returns the stored result and
changes nothing. A repeat with the same key but different details is refused.
"""

import dataclasses
import datetime
import hashlib
import json
import re
from decimal import Decimal

from django.db import connection, transaction

from . import numeric
from .errors import RetryKeyConflict, ValidationFailed
from .models import CommandRecord

_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,64}$")


def _plain(value):
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _plain(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, Decimal):
        # Normalise so 100, 100.0 and 100.0000 hash the same.
        return format(value.normalize(), "f")
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, float):
        raise TypeError("floats are not allowed in command payloads")
    return value


def payload_hash(payload) -> str:
    text = json.dumps(_plain(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def run_once(*, command: str, retry_key: str, payload, actor, action):
    """Run ``action`` at most once for ``retry_key``.

    ``action`` is called inside a transaction and must return a JSON-friendly
    dict. Returns ``(result, replayed)``. If ``action`` raises, the whole
    transaction (including the key) rolls back, so a corrected request can
    reuse the key.
    """
    if not retry_key or not _KEY_PATTERN.match(retry_key):
        raise ValidationFailed(["A retry key (8 to 64 letters, digits or - . _ :) is required for this action."])
    digest = payload_hash(payload)
    with transaction.atomic():
        with connection.cursor() as cursor:
            # ON CONFLICT waits for a concurrent request holding the same key
            # to commit or roll back, then tells us whether we own the key.
            cursor.execute(
                """
                INSERT INTO core_commandrecord (retry_key, command, payload_hash, actor_id, result, created_at)
                VALUES (%s, %s, %s, %s, '{}'::jsonb, now())
                ON CONFLICT (retry_key) DO NOTHING
                RETURNING id
                """,
                [retry_key, command, digest, actor.pk],
            )
            row = cursor.fetchone()
        if row is None:
            record = CommandRecord.objects.get(retry_key=retry_key)
            if record.command != command or record.payload_hash != digest or record.actor_id != actor.pk:
                raise RetryKeyConflict()
            return record.result, True
        result = action()
        CommandRecord.objects.filter(pk=row[0]).update(result=result)
        return result, False


__all__ = ["run_once", "payload_hash", "numeric"]
