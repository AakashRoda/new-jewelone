from django import forms
from django.db.models import Q
from django.forms import formset_factory

from accounts.models import User
from core import numeric
from masters.models import Item, Karigar, Location, Purity, Supplier, Variety

from .models import Inward
from .services import InwardInput, InwardLineInput


def weight_input(label: str, required: bool = False) -> forms.DecimalField:
    # Django refuses more decimal places than stored instead of rounding them away.
    return forms.DecimalField(
        label=label,
        required=required,
        max_digits=numeric.WEIGHT_MAX_DIGITS,
        decimal_places=numeric.WEIGHT_DECIMAL_PLACES,
        widget=forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off", "class": "num"}),
    )


def pieces_input(label: str) -> forms.IntegerField:
    return forms.IntegerField(
        label=label,
        required=False,
        min_value=0,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off", "class": "num"}),
    )


class InwardHeaderForm(forms.Form):
    source_type = forms.ChoiceField(label="Goods came from", choices=Inward.SOURCE_TYPES)
    supplier = forms.ModelChoiceField(label="Supplier", queryset=Supplier.objects.none(), required=False)
    karigar = forms.ModelChoiceField(label="Karigar", queryset=Karigar.objects.none(), required=False)
    source_reference = forms.CharField(
        label="Their reference", required=False, max_length=80, help_text="Challan, approval memo or slip number."
    )
    source_date = forms.DateField(
        label="Date on their document", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    location = forms.ModelChoiceField(label="Received at", queryset=Location.objects.none())
    custodian = forms.ModelChoiceField(
        label="In whose custody", queryset=User.objects.none(), required=False, help_text="Optional."
    )
    notes = forms.CharField(label="Notes", required=False, widget=forms.Textarea(attrs={"rows": 2}))
    reason = forms.CharField(
        label="Reason for this edit",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Required. It is kept in the history with the old and new values.",
    )

    def __init__(self, *args, inward: Inward | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        keep = lambda field: Q(pk=getattr(inward, field)) if inward is not None else Q(pk__in=[])  # noqa: E731
        self.fields["supplier"].queryset = Supplier.objects.filter(Q(is_active=True) | keep("supplier_id"))
        self.fields["karigar"].queryset = Karigar.objects.filter(Q(is_active=True) | keep("karigar_id"))
        self.fields["location"].queryset = Location.objects.filter(Q(is_active=True) | keep("location_id"))
        self.fields["custodian"].queryset = User.objects.filter(is_active=True).order_by("username")
        self.fields["custodian"].label_from_instance = lambda user: user.label
        if inward is None:
            del self.fields["reason"]
        else:
            self.fields["reason"].required = True


class InwardLineForm(forms.Form):
    id = forms.IntegerField(required=False, widget=forms.HiddenInput)
    item = forms.ModelChoiceField(label="Item", queryset=Item.objects.none())
    purity = forms.ModelChoiceField(label="Purity", queryset=Purity.objects.none())
    variety = forms.ModelChoiceField(
        label="Variety", queryset=Variety.objects.none(), required=False, empty_label="Not chosen yet"
    )
    declared_pieces = pieces_input("Declared pieces")
    declared_gross_weight = weight_input("Declared gross")
    declared_net_weight = weight_input("Declared net")
    actual_pieces = pieces_input("Actual pieces")
    actual_gross_weight = weight_input("Actual gross", required=True)
    actual_net_weight = weight_input("Actual net")
    condition_notes = forms.CharField(
        label="Condition notes",
        required=False,
        widget=forms.Textarea(attrs={"rows": 1}),
        help_text="Damaged pieces and anything else noticed. Record them here; they are still received.",
    )

    def __init__(self, *args, stock_mode: str, used_item_ids=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.stock_mode = stock_mode
        self.fields["item"].queryset = Item.objects.filter(stock_mode=stock_mode).filter(
            Q(is_active=True) | Q(pk__in=used_item_ids)
        )
        self.fields["purity"].queryset = Purity.objects.filter(is_active=True) | Purity.objects.filter(
            pk__in=[self.initial.get("purity")] if self.initial.get("purity") else []
        )
        self.fields["variety"].queryset = Variety.objects.filter(item__stock_mode=stock_mode).select_related("item")
        if stock_mode == Item.WEIGHT_ONLY:
            for name in ("declared_pieces", "declared_net_weight", "actual_pieces", "actual_net_weight"):
                del self.fields[name]
            self.fields["declared_gross_weight"].label = "Declared weight"
            self.fields["actual_gross_weight"].label = "Actual weight"

    def to_input(self) -> InwardLineInput:
        data = self.cleaned_data
        return InwardLineInput(
            id=data.get("id"),
            item_id=data["item"].pk,
            purity_id=data["purity"].pk,
            variety_id=data["variety"].pk if data.get("variety") else None,
            declared_pieces=data.get("declared_pieces"),
            declared_gross_weight=data.get("declared_gross_weight"),
            declared_net_weight=data.get("declared_net_weight"),
            actual_pieces=data.get("actual_pieces"),
            actual_gross_weight=data["actual_gross_weight"],
            actual_net_weight=data.get("actual_net_weight"),
            condition_notes=data.get("condition_notes", ""),
        )


def line_formset_class(extra: int):
    return formset_factory(InwardLineForm, extra=extra, can_delete=True)


def build_input(header: InwardHeaderForm, formset, stock_mode: str) -> InwardInput:
    data = header.cleaned_data
    lines = tuple(
        form.to_input()
        for form in formset.forms
        if form.has_changed() and form.cleaned_data and not form.cleaned_data.get("DELETE")
    )
    return InwardInput(
        source_type=data["source_type"],
        stock_mode=stock_mode,
        supplier_id=data["supplier"].pk if data.get("supplier") else None,
        karigar_id=data["karigar"].pk if data.get("karigar") else None,
        source_reference=data.get("source_reference", ""),
        source_date=data.get("source_date"),
        location_id=data["location"].pk,
        custodian_id=data["custodian"].pk if data.get("custodian") else None,
        notes=data.get("notes", ""),
        lines=lines,
    )


def line_initial(line) -> dict:
    return {
        "id": line.pk,
        "item": line.item_id,
        "purity": line.purity_id,
        "variety": line.variety_id,
        "declared_pieces": line.declared_pieces,
        "declared_gross_weight": line.declared_gross_weight,
        "declared_net_weight": line.declared_net_weight,
        "actual_pieces": line.actual_pieces,
        "actual_gross_weight": line.actual_gross_weight,
        "actual_net_weight": line.actual_net_weight,
        "condition_notes": line.condition_notes,
    }
