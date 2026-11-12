"""Masters and settings screens.

One generic list/create/edit flow serves every master. Records are never
deleted from here: a master that should no longer be picked is made inactive,
so receipts that already use it keep their history.
"""

from django.contrib import messages
from django.forms import modelform_factory
from django.forms.models import model_to_dict
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from audit import services as audit
from core.decisions import GATED_BY_OPEN_DECISIONS
from core.web import forbidden

from .models import (
    ChargeDefinition,
    HsnCode,
    Item,
    Karigar,
    Location,
    MakingChargeRule,
    Metal,
    PolicySetting,
    Purity,
    Supplier,
    Unit,
    Variety,
)

MASTERS = {
    "metals": (Metal, ["name", "is_active"], "Metals", ""),
    "purities": (Purity, ["name", "metal", "percentage", "is_active"], "Purities", ""),
    "items": (Item, ["name", "stock_mode", "weight_unit", "hsn", "is_active"], "Items", ""),
    "varieties": (Variety, ["item", "name", "is_active"], "Varieties", ""),
    "units": (Unit, ["code", "name", "kind", "grams_per_unit", "is_active"], "Units", ""),
    "hsn": (HsnCode, ["code", "description", "is_active"], "HSN references", ""),
    "making-charge-rules": (
        MakingChargeRule,
        ["name", "applies_to", "item", "description", "is_active"],
        "Making-charge rules",
        "Names only for now. Charge units, bases and rounding are not decided (O03).",
    ),
    "other-charges": (
        ChargeDefinition,
        ["name", "description", "is_active"],
        "Other-charge definitions",
        "Charge types created by the business. How they are calculated is not decided (O03).",
    ),
    "suppliers": (Supplier, ["name", "gstin", "phone", "notes", "is_active"], "Suppliers", ""),
    "karigars": (Karigar, ["name", "phone", "notes", "is_active"], "Karigars", ""),
    "locations": (
        Location,
        ["name", "is_demo", "is_active"],
        "Locations",
        "The real location list is not decided (O06).",
    ),
}
CAPABILITY = "masters.manage"


def _master(slug: str):
    if slug not in MASTERS:
        raise Http404
    model, fields, title, note = MASTERS[slug]
    return model, fields, title, note


def _plain(instance, fields) -> dict:
    return {name: str(value) if value is not None else None for name, value in model_to_dict(instance, fields=fields).items()}


def masters_index(request):
    groups = [
        {"slug": slug, "title": title, "count": model.objects.count(), "note": note}
        for slug, (model, _fields, title, note) in MASTERS.items()
    ]
    return render(
        request,
        "masters/index.html",
        {
            "groups": groups,
            "settings_rows": PolicySetting.objects.all(),
            "gated": GATED_BY_OPEN_DECISIONS,
        },
    )


def master_list(request, slug: str):
    model, fields, title, note = _master(slug)
    columns = [(name, model._meta.get_field(name).verbose_name) for name in fields]
    rows = [
        {"pk": obj.pk, "cells": [_cell(obj, name) for name in fields], "is_active": obj.is_active}
        for obj in model.objects.all()
    ]
    return render(
        request,
        "masters/list.html",
        {"slug": slug, "title": title, "note": note, "columns": columns, "rows": rows},
    )


def _cell(obj, name):
    display = getattr(obj, f"get_{name}_display", None)
    value = display() if display else getattr(obj, name)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return "—" if value is None or value == "" else value


@require_http_methods(["GET", "POST"])
def master_edit(request, slug: str, pk: int | None = None):
    model, fields, title, note = _master(slug)
    if not request.user.has_capability(CAPABILITY):
        return forbidden(request, CAPABILITY)
    instance = get_object_or_404(model, pk=pk) if pk else None
    Form = modelform_factory(model, fields=fields)
    before = _plain(instance, fields) if instance else None
    form = Form(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        # Checked again at the moment of saving, not only when the page was opened.
        if not request.user.has_capability(CAPABILITY):
            return forbidden(request, CAPABILITY)
        saved = form.save()
        audit.record(
            actor=request.user,
            action="master.update" if instance else "master.create",
            capability=CAPABILITY,
            target=saved,
            payload={"before": before, "after": _plain(saved, fields)},
        )
        messages.success(request, f"{saved} saved.")
        return redirect("master-list", slug=slug)
    return render(
        request,
        "masters/form.html",
        {"slug": slug, "title": title, "note": note, "form": form, "instance": instance},
        status=422 if request.method == "POST" else 200,
    )
