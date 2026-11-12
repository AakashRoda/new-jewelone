from django.contrib.auth.models import AbstractUser
from django.db import models


class Capability(models.Model):
    key = models.CharField(max_length=64, unique=True)
    description = models.CharField(max_length=200)

    class Meta:
        ordering = ["key"]
        verbose_name_plural = "capabilities"

    def __str__(self):
        return self.key


class Role(models.Model):
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=200, blank=True)
    is_demo = models.BooleanField(
        default=False, help_text="Demo configuration, not an agreed production grant (O12)."
    )
    capabilities = models.ManyToManyField(Capability, blank=True, related_name="roles")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Store staff member.

    Django's own permission flags (is_superuser, is_staff, groups) are not
    used for business actions. Only capabilities reached through roles count.
    """

    roles = models.ManyToManyField(Role, blank=True, related_name="users")

    def capability_keys(self) -> set[str]:
        """Read the user's current capabilities from the database.

        Deliberately not cached on the instance: permissions are checked at
        action time against the current configuration.
        """
        if not self.is_active:
            return set()
        return set(
            Capability.objects.filter(roles__users=self).values_list("key", flat=True).distinct()
        )

    def has_capability(self, key: str) -> bool:
        return key in self.capability_keys()

    @property
    def label(self) -> str:
        return self.get_full_name() or self.username
