from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from demo import fixtures


class Command(BaseCommand):
    help = "Load synthetic masters, demo roles/users and the demo stock scenarios. Safe to run again."

    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError(
                "Refusing to load demo data: STOREAPP_DEMO_MODE is off. Demo users and synthetic "
                "stock must never be loaded next to real stock."
            )
        seeded = fixtures.seed_all()
        self.stdout.write(self.style.SUCCESS("Demo data is in place."))
        self.stdout.write(f"  Inwards: {seeded.t01.inward}, {seeded.t08}, {seeded.t02}, {seeded.t07}, {seeded.draft} (draft)")
        self.stdout.write(f"  Demo logins ({', '.join(fixtures.DEMO_USERS)}) use the password: {fixtures.DEMO_PASSWORD}")
