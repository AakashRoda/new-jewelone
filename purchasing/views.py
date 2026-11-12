from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from audit import services as audit
from core.errors import DomainError
from core.web import capability_required, error_messages, new_retry_key
from inventory.models import Inward, InwardLine

from . import services
from .forms import InvoiceHeaderForm, InvoiceLineFormSet, RemoveMatchForm, build_input
from .models import InvoiceMatch, SupplierInvoice, SupplierInvoiceLine


def invoice_list(request):
    invoices = SupplierInvoice.objects.select_related("supplier").annotate(line_count=Count("lines"))[:200]
    return render(request, "purchasing/invoice_list.html", {"invoices": invoices})


def invoice_detail(request, pk: int):
    invoice = get_object_or_404(SupplierInvoice.objects.select_related("supplier", "created_by"), pk=pk)
    lines = list(
        invoice.lines.select_related("item", "purity", "unit").prefetch_related(
            "matches__inward_line__inward", "matches__inward_line__item", "matches__inward_line__unit"
        )
    )
    for line in lines:
        line.links = [m for m in line.matches.all() if m.removed_at is None]
    return render(
        request,
        "purchasing/invoice_detail.html",
        {"invoice": invoice, "lines": lines, "history": audit.history_for(invoice)},
    )


@capability_required("purchase_invoice.record")
@require_http_methods(["GET", "POST"])
def invoice_new(request):
    if request.method == "POST":
        header = InvoiceHeaderForm(request.POST)
        formset = InvoiceLineFormSet(request.POST, prefix="lines")
        retry_key = request.POST.get("retry_key", "")
        errors: list[str] = []
        if header.is_valid() and formset.is_valid():
            try:
                invoice = services.record_supplier_invoice(
                    actor=request.user, data=build_input(header, formset), retry_key=retry_key
                )
            except DomainError as exc:
                errors = error_messages(exc)
            else:
                messages.success(request, f"{invoice} entered as a book record. Physical stock is unchanged.")
                return redirect("invoice-detail", pk=invoice.pk)
        return render(
            request,
            "purchasing/invoice_form.html",
            {"header": header, "formset": formset, "retry_key": retry_key, "errors": errors},
            status=422,
        )
    return render(
        request,
        "purchasing/invoice_form.html",
        {
            "header": InvoiceHeaderForm(),
            "formset": InvoiceLineFormSet(prefix="lines"),
            "retry_key": new_retry_key(),
            "errors": [],
        },
    )


@capability_required("purchase_invoice.match")
@require_http_methods(["GET", "POST"])
def match_pick(request, line_pk: int):
    """Choose which existing receipt line an invoice line refers to."""
    invoice_line = get_object_or_404(
        SupplierInvoiceLine.objects.select_related("invoice", "invoice__supplier", "item", "unit"), pk=line_pk
    )
    invoice = invoice_line.invoice
    errors: list[str] = []
    retry_key = new_retry_key()
    if request.method == "POST":
        retry_key = request.POST.get("retry_key", "")
        try:
            services.match_invoice_line(
                actor=request.user,
                invoice_line_id=invoice_line.pk,
                inward_line_id=int(request.POST.get("inward_line") or 0),
                retry_key=retry_key,
            )
        except DomainError as exc:
            errors = error_messages(exc)
        else:
            messages.success(request, "Invoice line linked to the receipt. Physical stock is unchanged.")
            return redirect("invoice-detail", pk=invoice.pk)
    linked = set(
        InvoiceMatch.objects.filter(invoice_line=invoice_line, removed_at__isnull=True).values_list(
            "inward_line_id", flat=True
        )
    )
    candidates = (
        InwardLine.objects.filter(
            inward__supplier=invoice.supplier,
            inward__status=Inward.CONFIRMED,
            inward__source_type__in=Inward.SUPPLIER_SOURCES,
            is_removed=False,
        )
        .exclude(pk__in=linked)
        .select_related("inward", "item", "purity", "variety", "unit")
        .order_by("-inward_id", "line_no")
    )
    return render(
        request,
        "purchasing/match_pick.html",
        {
            "invoice": invoice,
            "invoice_line": invoice_line,
            "candidates": candidates,
            "retry_key": retry_key,
            "errors": errors,
        },
        status=422 if errors else 200,
    )


@capability_required("purchase_invoice.match")
@require_http_methods(["GET", "POST"])
def match_remove(request, match_pk: int):
    match = get_object_or_404(
        InvoiceMatch.objects.select_related("invoice_line__invoice", "inward_line__inward"), pk=match_pk
    )
    invoice = match.invoice_line.invoice
    errors: list[str] = []
    retry_key = new_retry_key()
    form = RemoveMatchForm(request.POST or None)
    if request.method == "POST":
        retry_key = request.POST.get("retry_key", "")
        if form.is_valid():
            try:
                services.remove_invoice_match(
                    actor=request.user, match_id=match.pk, reason=form.cleaned_data["reason"], retry_key=retry_key
                )
            except DomainError as exc:
                errors = error_messages(exc)
            else:
                messages.success(request, "Link removed. Physical stock is unchanged.")
                return redirect("invoice-detail", pk=invoice.pk)
    return render(
        request,
        "purchasing/match_remove.html",
        {"match": match, "invoice": invoice, "form": form, "retry_key": retry_key, "errors": errors},
        status=422 if request.method == "POST" else 200,
    )
