"""Server-side capability checks used by every command and guarded screen."""

import functools

from audit import services as audit
from core.errors import CapabilityDenied


def require(actor, capability: str, *, action: str, target=None) -> None:
    """Raise CapabilityDenied unless ``actor`` currently holds ``capability``."""
    if actor is None or not actor.is_authenticated or not actor.has_capability(capability):
        raise CapabilityDenied(capability, action, target)


def records_denials(func):
    """Write a 'denied' audit event when a command refuses for lack of permission.

    The event is written after the command's own transaction has rolled back,
    so the refusal is kept even though nothing else changed.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CapabilityDenied as denied:
            audit.record(
                actor=kwargs.get("actor"),
                action=denied.action,
                outcome=audit.DENIED,
                capability=denied.capability,
                target=denied.target,
                retry_key=kwargs.get("retry_key", "") or "",
            )
            raise

    return wrapper
