"""Errors raised by business commands.

Screens catch DomainError and show its message next to the form the operator
was filling in, so messages are written for store staff, not developers.
"""


class DomainError(Exception):
    code = "domain_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class CapabilityDenied(DomainError):
    code = "capability_denied"

    def __init__(self, capability: str, action: str, target=None):
        super().__init__(f"You do not have the permission needed for this action ({capability}).")
        self.capability = capability
        self.action = action
        self.target = target


class ValidationFailed(DomainError):
    code = "validation_failed"

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = list(errors)


class StaleVersion(DomainError):
    code = "stale_version"

    def __init__(self, what: str):
        super().__init__(
            f"{what} was changed by someone else after you opened it. Reload it, check the current values and try again."
        )


class RetryKeyConflict(DomainError):
    code = "retry_key_conflict"

    def __init__(self):
        super().__init__(
            "This request was already submitted with different details. Reload the page and submit again."
        )


class InwardLocked(DomainError):
    code = "inward_locked"


class InvalidState(DomainError):
    code = "invalid_state"
