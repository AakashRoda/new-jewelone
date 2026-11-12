from django.core.management.base import BaseCommand, CommandError

from accounts.models import Capability, Role, User
from audit import services as audit

ROLE_NAME = "Full access"


class Command(BaseCommand):
    help = (
        "Give an existing user a 'Full access' role holding every capability. "
        "Meant for setting up the first user of a new installation from the server; "
        "afterwards roles are managed on the Users and roles screen."
    )

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, username, **options):
        user = User.objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"No user named {username}. Create one first with: manage.py createsuperuser")
        role, _ = Role.objects.get_or_create(
            name=ROLE_NAME, defaults={"description": "Every capability. Granted from the server command line."}
        )
        role.capabilities.set(Capability.objects.all())
        user.roles.add(role)
        audit.record(
            actor=None,
            action="user.grant_full_access",
            target=user,
            payload={"role": ROLE_NAME, "granted_from": "server command line"},
        )
        self.stdout.write(self.style.SUCCESS(f"{username} now holds the '{ROLE_NAME}' role."))
