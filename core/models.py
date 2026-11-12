from django.conf import settings
from django.db import models

from . import numeric


def weight_field(**kwargs) -> models.DecimalField:
    return models.DecimalField(
        max_digits=numeric.WEIGHT_MAX_DIGITS, decimal_places=numeric.WEIGHT_DECIMAL_PLACES, **kwargs
    )


def money_field(**kwargs) -> models.DecimalField:
    return models.DecimalField(
        max_digits=numeric.MONEY_MAX_DIGITS, decimal_places=numeric.MONEY_DECIMAL_PLACES, **kwargs
    )


def percent_field(**kwargs) -> models.DecimalField:
    return models.DecimalField(
        max_digits=numeric.PERCENT_MAX_DIGITS, decimal_places=numeric.PERCENT_DECIMAL_PLACES, **kwargs
    )


class CommandRecord(models.Model):
    """One row per accepted stock-changing or book-changing request.

    The retry key makes a repeated submission (double-click, network retry)
    return the original result instead of applying the command twice.
    """

    retry_key = models.CharField(max_length=64, unique=True)
    command = models.CharField(max_length=64)
    payload_hash = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.command} {self.retry_key}"
