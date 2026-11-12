from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from audit import services as audit
from core.errors import DomainError
from core.web import error_messages, forbidden, new_retry_key
from masters.models import Item

from . import queries, services
from .forms import InwardHeaderForm, build_input, line_formset_class, line_initial
from .models import Inward, StockMovement

MODE_LABELS = {Item.TAGGABLE: "Tagged pieces", Item.WEIGHT_ONLY: "Weight-only stock"}


def stock_overview(request):
    awaiting = list(queries.received_awaiting_lots())
    totals = {"pieces": 0, "gross": 0, "net": 0}
    for line in awaiting:
        totals["pieces"] += line.actual_pieces or 0
        totals["gross"] += line.actual_gross_weight
        totals["net"] += line.actual_net_weight or 0
    return render(
        request,
        "inventory/stock_overview.html",
        {
            "weight_only": queries.weight_only_balances(),
            "awaiting": awaiting,
            "awaiting_totals": totals,
            "drafts": Inward.objects.filter(status=Inward.DRAFT).count(),
        },
    )


def inward_list(request):
    inwards = (
        Inward.objects.select_related("supplier", "karigar", "location")
        .annotate(
            line_count=Count("lines", filter=Q(lines__is_removed=False)),
            total_weight=Sum("lines__actual_gross_weight", filter=Q(lines__is_removed=False)),
        )
        .order_by("-id")
    )
    status = request.GET.get("status", "")
    if status in dict(Inward.STATUSES):
        inwards = inwards.filter(status=status)
    return render(request, "inventory/inward_list.html", {"inwards": inwards[:200], "status": status})


def _detail_context(inward: Inward) -> dict:
    lines = list(
        inward.lines.select_related("item", "purity", "variety", "unit").prefetch_related(
            "invoice_matches__invoice_line__invoice"
        )
    )
    for line in lines:
        line.links = [m for m in line.invoice_matches.all() if m.removed_at is None]
    return {
        "inward": inward,
        "lines": [line for line in lines if not line.is_removed],
        "removed_lines": [line for line in lines if line.is_removed],
        "lock_explanation": services.lock_explanation(inward),
        "history": audit.history_for(inward),
        "movements": StockMovement.objects.filter(inward_line__inward=inward).select_related(
            "item", "unit", "actor", "inward_line"
        ),
        "mode_label": MODE_LABELS[inward.stock_mode],
    }


def inward_detail(request, pk: int):
    inward = get_object_or_404(
        Inward.objects.select_related("supplier", "karigar", "location", "custodian", "created_by", "confirmed_by"),
        pk=pk,
    )
    context = _detail_context(inward)
    user = request.user
    can_confirm = user.has_capability("inward.create") and (
        not inward.needs_parcel_opening or user.has_capability("parcel.open")
    )
    if inward.is_locked:
        edit_block = context["lock_explanation"]
    elif not user.has_capability("inward.edit"):
        edit_block = "You do not have permission to edit inwards (inward.edit)."
    else:
        edit_block = ""
    confirm_block = ""
    if not inward.is_confirmed and not can_confirm:
        confirm_block = (
            "Only someone allowed to open and verify supplier parcels (parcel.open) can receive this into stock."
            if inward.needs_parcel_opening and user.has_capability("inward.create")
            else "You do not have permission to receive goods into stock (inward.create)."
        )
    context.update(
        {"edit_block": edit_block, "can_confirm": can_confirm and not inward.is_confirmed, "confirm_block": confirm_block}
    )
    return render(request, "inventory/inward_detail.html", context)


def _render_form(request, *, inward, stock_mode, header, formset, retry_key, errors, status=200):
    return render(
        request,
        "inventory/inward_form.html",
        {
            "inward": inward,
            "stock_mode": stock_mode,
            "mode_label": MODE_LABELS[stock_mode],
            "weight_only": stock_mode == Item.WEIGHT_ONLY,
            "header": header,
            "formset": formset,
            "retry_key": retry_key,
            "errors": errors,
            "expected_version": request.POST.get("expected_version") or (inward.version if inward else ""),
        },
        status=status,
    )


@require_http_methods(["GET", "POST"])
def inward_new(request, stock_mode: str):
    if stock_mode not in MODE_LABELS:
        raise Http404
    if not request.user.has_capability("inward.create"):
        return forbidden(request, "inward.create")
    form_kwargs = {"stock_mode": stock_mode}
    LineFormSet = line_formset_class(extra=1)
    if request.method == "POST":
        header = InwardHeaderForm(request.POST)
        formset = LineFormSet(request.POST, prefix="lines", form_kwargs=form_kwargs)
        retry_key = request.POST.get("retry_key", "")
        errors: list[str] = []
        if header.is_valid() and formset.is_valid():
            try:
                inward = services.create_inward(
                    actor=request.user, data=build_input(header, formset, stock_mode), retry_key=retry_key
                )
            except DomainError as exc:
                errors = error_messages(exc)
            else:
                messages.success(request, f"{inward} saved as a draft. It is not in stock until it is received.")
                return redirect("inward-detail", pk=inward.pk)
        return _render_form(
            request, inward=None, stock_mode=stock_mode, header=header, formset=formset,
            retry_key=retry_key, errors=errors, status=422,
        )
    header = InwardHeaderForm(initial={"source_type": Inward.SUPPLIER_PURCHASE})
    formset = LineFormSet(prefix="lines", form_kwargs=form_kwargs)
    return _render_form(
        request, inward=None, stock_mode=stock_mode, header=header, formset=formset,
        retry_key=new_retry_key(), errors=[],
    )


@require_http_methods(["GET", "POST"])
def inward_edit(request, pk: int):
    inward = get_object_or_404(Inward, pk=pk)
    if not request.user.has_capability("inward.edit"):
        return forbidden(request, "inward.edit")
    if inward.is_locked:
        messages.error(request, services.lock_explanation(inward))
        return redirect("inward-detail", pk=inward.pk)
    current_lines = [line for line in inward.lines.order_by("line_no") if not line.is_removed]
    form_kwargs = {"stock_mode": inward.stock_mode, "used_item_ids": [line.item_id for line in current_lines]}
    LineFormSet = line_formset_class(extra=0)
    if request.method == "POST":
        header = InwardHeaderForm(request.POST, inward=inward)
        formset = LineFormSet(request.POST, prefix="lines", form_kwargs=form_kwargs)
        retry_key = request.POST.get("retry_key", "")
        errors: list[str] = []
        if header.is_valid() and formset.is_valid():
            try:
                services.edit_inward(
                    actor=request.user,
                    inward_id=inward.pk,
                    data=build_input(header, formset, inward.stock_mode),
                    reason=header.cleaned_data["reason"],
                    expected_version=int(request.POST.get("expected_version") or 0),
                    retry_key=retry_key,
                )
            except DomainError as exc:
                errors = error_messages(exc)
            else:
                messages.success(request, f"{inward} updated. The reason and the old values are in its history.")
                return redirect("inward-detail", pk=inward.pk)
        return _render_form(
            request, inward=inward, stock_mode=inward.stock_mode, header=header, formset=formset,
            retry_key=retry_key, errors=errors, status=422,
        )
    header = InwardHeaderForm(
        inward=inward,
        initial={
            "source_type": inward.source_type,
            "supplier": inward.supplier_id,
            "karigar": inward.karigar_id,
            "source_reference": inward.source_reference,
            "source_date": inward.source_date,
            "location": inward.location_id,
            "custodian": inward.custodian_id,
            "notes": inward.notes,
        },
    )
    formset = LineFormSet(
        prefix="lines", form_kwargs=form_kwargs, initial=[line_initial(line) for line in current_lines]
    )
    return _render_form(
        request, inward=inward, stock_mode=inward.stock_mode, header=header, formset=formset,
        retry_key=new_retry_key(), errors=[],
    )


@require_http_methods(["GET", "POST"])
def inward_confirm(request, pk: int):
    inward = get_object_or_404(Inward.objects.select_related("supplier", "karigar", "location"), pk=pk)
    if inward.is_confirmed and request.method == "GET":
        return redirect("inward-detail", pk=inward.pk)
    errors: list[str] = []
    retry_key = new_retry_key()
    if request.method == "POST":
        retry_key = request.POST.get("retry_key", "")
        try:
            services.confirm_inward(
                actor=request.user,
                inward_id=inward.pk,
                expected_version=int(request.POST.get("expected_version") or 0),
                retry_key=retry_key,
            )
        except DomainError as exc:
            errors = error_messages(exc)
            inward.refresh_from_db()
        else:
            messages.success(request, f"{inward} received into stock.")
            return redirect("inward-detail", pk=inward.pk)
    context = _detail_context(inward)
    context.update(
        {
            "errors": errors,
            "retry_key": retry_key,
            "expected_version": inward.version,
        }
    )
    return render(request, "inventory/inward_confirm.html", context, status=422 if errors else 200)
