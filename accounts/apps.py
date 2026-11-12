from django.apps import AppConfig
from django.db.models.signals import post_migrate


def sync_capabilities(sender, **kwargs):
    """Keep the capability table in step with the keys the code checks."""
    from .capabilities import CAPABILITIES
    from .models import Capability

    for key, description in CAPABILITIES.items():
        Capability.objects.update_or_create(key=key, defaults={"description": description})


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        post_migrate.connect(sync_capabilities, sender=self)
