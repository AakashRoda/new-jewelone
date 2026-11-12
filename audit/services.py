import datetime
from decimal import Decimal

from .models import AuditEvent

SUCCEEDED = AuditEvent.SUCCEEDED
DENIED = AuditEvent.DENIED


def jsonable(value):
    """Convert snapshots to JSON without losing decimal exactness (stored as text)."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, float):
        raise TypeError("floats are not allowed in audit payloads")
    return value


def record(
    *,
    actor,
    action: str,
    outcome: str = SUCCEEDED,
    capability: str = "",
    target=None,
    target_label: str = "",
    reason: str = "",
    payload: dict | None = None,
    retry_key: str = "",
) -> AuditEvent:
    target_type = ""
    target_id = None
    if target is not None:
        target_type = target._meta.label_lower
        target_id = target.pk
        target_label = target_label or str(target)
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        action=action,
        outcome=outcome,
        capability=capability,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label[:120],
        reason=reason,
        payload=jsonable(payload or {}),
        retry_key=retry_key,
    )


def history_for(target):
    return AuditEvent.objects.filter(
        target_type=target._meta.label_lower, target_id=target.pk
    ).select_related("actor")
