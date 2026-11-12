"""Book-side commands: RecordSupplierInvoice, MatchPurchaseInvoice, RemoveInvoiceMatch.

None of these create stock movements. Tests assert that the physical ledger is
unchanged by every one of them (T01, T08).
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.utils import timezone

from accounts.permissions import records_denials, require
from audit import services as audit
from core import numeric
from core.errors import InvalidState, ValidationFailed
from core.idempotency import run_once
from inventory.models import Inward, InwardLine
from masters.models import Item, Purity, Supplier

from .models import InvoiceMatch, SupplierInvoice, SupplierInvoiceLine

ZERO = Decimal("0")


@dataclass(frozen=True)
class InvoiceLineInput:
    description: str
    item_id: int | None = None
    purity_id: int | None = None
    hsn_code: str = ""
    stated_pieces: int | None = None
    stated_gross_weight: Decimal | None = None
    stated_net_weight: Decimal | None = None
    stated_value: Decimal | None = None


@dataclass(frozen=True)
class InvoiceInput:
    supplier_id: int
    invoice_number: str
    invoice_date: date
    lines: tuple[InvoiceLineInput, ...]
    stated_taxable_value: Decimal | None = None
    stated_tax_value: Decimal | None = None
    stated_total_value: Decimal | None = None
    notes: str = ""


def _number(value, places, what, errors):
    if value is None:
        return None
    try:
        number = numeric.to_decimal(value, places=places, what=what)
    except ValueError as exc:
        errors.append(str(exc))
        return None
    if number < ZERO:
        errors.append(f"{what} cannot be negative ({number}).")
    return number


@records_denials
def record_supplier_invoice(*, actor, data: InvoiceInput, retry_key: str) -> SupplierInvoice:
    """Enter the supplier's invoice as a book record. Adds no physical stock."""
    require(actor, "purchase_invoice.record", action="purchase_invoice.record")

    def action():
        errors: list[str] = []
        supplier = Supplier.objects.filter(pk=data.supplier_id).first()
        if supplier is None:
            errors.append("Choose the supplier who issued the invoice.")
        number = (data.invoice_number or "").strip()
        if not number:
            errors.append("Enter the supplier's invoice number.")
        if data.invoice_date is None:
            errors.append("Enter the invoice date.")
        if supplier and number and SupplierInvoice.objects.filter(supplier=supplier, invoice_number=number).exists():
            errors.append(f"Invoice {number} from {supplier} has already been entered.")
        if not data.lines:
            errors.append("Add at least one invoice line.")

        money = numeric.MONEY_DECIMAL_PLACES
        weight = numeric.WEIGHT_DECIMAL_PLACES
        header_values = {
            "stated_taxable_value": _number(data.stated_taxable_value, money, "Taxable value", errors),
            "stated_tax_value": _number(data.stated_tax_value, money, "Tax value", errors),
            "stated_total_value": _number(data.stated_total_value, money, "Invoice total", errors),
        }
        clean_lines = []
        for index, line in enumerate(data.lines, start=1):
            label = f"Line {index}"
            description = (line.description or "").strip()
            if not description:
                errors.append(f"{label}: enter the description as written on the invoice.")
            item = Item.objects.select_related("weight_unit").filter(pk=line.item_id).first() if line.item_id else None
            purity = Purity.objects.filter(pk=line.purity_id).first() if line.purity_id else None
            if line.item_id and item is None:
                errors.append(f"{label}: the chosen item does not exist.")
            if line.purity_id and purity is None:
                errors.append(f"{label}: the chosen purity does not exist.")
            clean_lines.append(
                {
                    "description": description,
                    "item": item,
                    "purity": purity,
                    "unit": item.weight_unit if item else None,
                    "hsn_code": (line.hsn_code or "").strip(),
                    "stated_pieces": line.stated_pieces,
                    "stated_gross_weight": _number(line.stated_gross_weight, weight, f"{label} stated weight", errors),
                    "stated_net_weight": _number(line.stated_net_weight, weight, f"{label} stated net weight", errors),
                    "stated_value": _number(line.stated_value, money, f"{label} stated value", errors),
                }
            )
        if errors:
            raise ValidationFailed(errors)

        invoice = SupplierInvoice.objects.create(
            supplier=supplier,
            invoice_number=number,
            invoice_date=data.invoice_date,
            notes=(data.notes or "").strip(),
            created_by=actor,
            **header_values,
        )
        for line_no, fields in enumerate(clean_lines, start=1):
            SupplierInvoiceLine.objects.create(invoice=invoice, line_no=line_no, **fields)
        audit.record(
            actor=actor,
            action="purchase_invoice.record",
            capability="purchase_invoice.record",
            target=invoice,
            payload={
                "supplier": supplier.name,
                "invoice_number": number,
                "invoice_date": data.invoice_date,
                "stated_total_value": header_values["stated_total_value"],
                "lines": len(clean_lines),
                "physical_stock_effect": "none",
            },
            retry_key=retry_key,
        )
        return {"invoice_id": invoice.pk}

    result, _ = run_once(
        command="RecordSupplierInvoice", retry_key=retry_key, payload=data, actor=actor, action=action
    )
    return SupplierInvoice.objects.get(pk=result["invoice_id"])


@records_denials
def match_invoice_line(*, actor, invoice_line_id: int, inward_line_id: int, retry_key: str) -> InvoiceMatch:
    """Link an invoice line to a receipt line that already exists.

    Matching the same pair again returns the existing link. No stock is added
    and no purchase metal rate is asked for.
    """
    require(actor, "purchase_invoice.match", action="purchase_invoice.match")

    def action():
        invoice_line = (
            SupplierInvoiceLine.objects.select_for_update(of=("self",))
            .select_related("invoice", "invoice__supplier")
            .filter(pk=invoice_line_id)
            .first()
        )
        inward_line = InwardLine.objects.select_related("inward").filter(pk=inward_line_id).first()
        if invoice_line is None or inward_line is None:
            raise InvalidState("The invoice line or the receipt line no longer exists.")
        inward = inward_line.inward
        if inward_line.is_removed:
            raise InvalidState(f"{inward_line} was removed from its inward and cannot be matched.")
        if not inward.is_confirmed:
            raise InvalidState(
                f"{inward} has not been received into stock yet. An invoice can only be matched to an existing receipt."
            )
        if inward.source_type not in Inward.SUPPLIER_SOURCES or inward.supplier_id != invoice_line.invoice.supplier_id:
            raise InvalidState(
                f"{inward} did not come from {invoice_line.invoice.supplier}, so it cannot be matched to this invoice."
            )
        existing = InvoiceMatch.objects.filter(
            invoice_line=invoice_line, inward_line=inward_line, removed_at__isnull=True
        ).first()
        if existing is not None:
            return {"match_id": existing.pk, "already_matched": True}
        match = InvoiceMatch.objects.create(invoice_line=invoice_line, inward_line=inward_line, created_by=actor)
        audit.record(
            actor=actor,
            action="purchase_invoice.match",
            capability="purchase_invoice.match",
            target=invoice_line.invoice,
            payload={
                "invoice_line": invoice_line.line_no,
                "inward": inward.number,
                "inward_line": inward_line.line_no,
                "physical_stock_effect": "none",
            },
            retry_key=retry_key,
        )
        return {"match_id": match.pk, "already_matched": False}

    payload = {"invoice_line_id": invoice_line_id, "inward_line_id": inward_line_id}
    result, _ = run_once(
        command="MatchPurchaseInvoice", retry_key=retry_key, payload=payload, actor=actor, action=action
    )
    return InvoiceMatch.objects.get(pk=result["match_id"])


@records_denials
def remove_invoice_match(*, actor, match_id: int, reason: str, retry_key: str) -> InvoiceMatch:
    """Take back a wrong link. The link row is kept with who removed it and why."""
    require(actor, "purchase_invoice.match", action="purchase_invoice.unmatch")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationFailed(["Give a clear reason for removing this link. It is kept in the history."])

    def action():
        match = (
            InvoiceMatch.objects.select_for_update(of=("self",))
            .select_related("invoice_line__invoice", "inward_line__inward")
            .filter(pk=match_id)
            .first()
        )
        if match is None:
            raise InvalidState("This link no longer exists.")
        if match.removed_at is not None:
            raise InvalidState("This link has already been removed.")
        match.removed_at = timezone.now()
        match.removed_by = actor
        match.removal_reason = reason
        match.save(update_fields=["removed_at", "removed_by", "removal_reason"])
        audit.record(
            actor=actor,
            action="purchase_invoice.unmatch",
            capability="purchase_invoice.match",
            target=match.invoice_line.invoice,
            reason=reason,
            payload={
                "invoice_line": match.invoice_line.line_no,
                "inward": match.inward_line.inward.number,
                "inward_line": match.inward_line.line_no,
                "physical_stock_effect": "none",
            },
            retry_key=retry_key,
        )
        return {"match_id": match.pk}

    payload = {"match_id": match_id, "reason": reason}
    run_once(command="RemoveInvoiceMatch", retry_key=retry_key, payload=payload, actor=actor, action=action)
    return InvoiceMatch.objects.get(pk=match_id)

