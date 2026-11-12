import json

from django.core.management.base import BaseCommand

from audit.models import AuditEvent
from inventory import queries
from inventory.models import Inward, StockMovement
from purchasing.models import InvoiceMatch, SupplierInvoice


class Command(BaseCommand):
    help = "Print a JSON summary of stock and record counts. Used to compare data before and after a restart or reload."

    def handle(self, *args, **options):
        summary = {
            "inwards": Inward.objects.count(),
            "inwards_confirmed": Inward.objects.filter(status=Inward.CONFIRMED).count(),
            "inwards_locked": Inward.objects.filter(locked_at__isnull=False).count(),
            "stock_movements": StockMovement.objects.count(),
            "supplier_invoices": SupplierInvoice.objects.count(),
            "active_invoice_matches": InvoiceMatch.objects.filter(removed_at__isnull=True).count(),
            "audit_events": AuditEvent.objects.count(),
            "weight_only_balances": [
                {**row, "weight": str(row["weight"])} for row in queries.weight_only_balances()
            ],
            "physical_totals": [
                {k: (str(v) if v is not None and k.endswith("weight") else v) for k, v in row.items()}
                for row in queries.physical_totals()
            ],
        }
        self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))
