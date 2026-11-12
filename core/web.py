"""Small helpers shared by the screens."""

import functools
import uuid

from django.shortcuts import render

from core.errors import DomainError, ValidationFailed


def new_retry_key() -> str:
    return uuid.uuid4().hex


def error_messages(exc: DomainError) -> list[str]:
    if isinstance(exc, ValidationFailed):
        return exc.errors
    return [exc.message]


def forbidden(request, capability: str):
    return render(request, "forbidden.html", {"capability": capability}, status=403)


def capability_required(capability: str):
    """Guard a screen. Commands behind the screen check again at action time."""

    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.has_capability(capability):
                return forbidden(request, capability)
            return view(request, *args, **kwargs)

        return wrapper

    return decorator
