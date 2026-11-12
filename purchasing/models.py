"""Book records: what the supplier's invoice states (C02).

Nothing in this app adds, removes or changes physical stock. An invoice can be
entered before or after the goods are received, and a receipt never needs an
invoice. There is deliberately no purchase metal rate anywhere (C06).

Full purchase accounting, settlement and GST treatment are deferred (O11).
"""

from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import money_field, weight_field
from inventory.models import InwardLine
from masters.models import Item, Purity, Supplier, Unit


class SupplierInvoice(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="invoices")
    invoice_number = models.CharField(max_length=60)
    invoice_date = models.DateField()
    # Values as stated on the supplier's document. Empty means not entered, never zero.
    stated_taxable_value = money_field(null=True, blank=True)
    stated_tax_value = money_field(null=True, blank=True)
    stated_total_value = money_field(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-invoice_date", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["supplier", "invoice_number"], name="supplier_invoice_number_unique"),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number}"


class SupplierInvoiceLine(models.Model):
    invoice = models.ForeignKey(SupplierInvoice, on_delete=models.PROTECT, related_name="lines")
    line_no = models.PositiveIntegerField()
    description = models.CharField(max_length=200)
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    purity = models.ForeignKey(Purity, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    hsn_code = models.CharField(max_length=12, blank=True)
    unit = models.ForeignKey(Unit, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    stated_pieces = models.PositiveIntegerField(null=True, blank=True)
    stated_gross_weight = weight_field(null=True, blank=True)
    stated_net_weight = weight_field(null=True, blank=True)
    stated_value = money_field(null=True, blank=True)

    class Meta:
        ordering = ["invoice_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["invoice", "line_no"], name="supplier_invoice_line_no_unique"),
        ]

    def __str__(self):
        return f"{self.invoice} line {self.line_no}"

    def active_matches(self):
        return [m for m in self.matches.all() if m.removed_at is None]


class InvoiceMatch(models.Model):
    """A link between an invoice line and a receipt line that already exists.

    It is a cross-reference only. It carries no quantity of its own and has no
    physical stock effect.
    """

    invoice_line = models.ForeignKey(SupplierInvoiceLine, on_delete=models.PROTECT, related_name="matches")
    inward_line = models.ForeignKey(InwardLine, on_delete=models.PROTECT, related_name="invoice_matches")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True)
    removed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    removal_reason = models.TextField(blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["invoice_line", "inward_line"],
                condition=Q(removed_at__isnull=True),
                name="one_active_match_per_invoice_and_receipt_line",
            ),
        ]

    def __str__(self):
        return f"{self.invoice_line} ↔ {self.inward_line}"
