from django import forms
from django.forms import formset_factory

from core import numeric
from inventory.forms import pieces_input, weight_input
from masters.models import Item, Purity, Supplier

from .services import InvoiceInput, InvoiceLineInput


def money_input(label: str) -> forms.DecimalField:
    return forms.DecimalField(
        label=label,
        required=False,
        min_value=0,
        max_digits=numeric.MONEY_MAX_DIGITS,
        decimal_places=numeric.MONEY_DECIMAL_PLACES,
        widget=forms.TextInput(attrs={"inputmode": "decimal", "autocomplete": "off", "class": "num"}),
    )


class InvoiceHeaderForm(forms.Form):
    supplier = forms.ModelChoiceField(label="Supplier", queryset=Supplier.objects.filter(is_active=True))
    invoice_number = forms.CharField(label="Invoice number", max_length=60)
    invoice_date = forms.DateField(label="Invoice date", widget=forms.DateInput(attrs={"type": "date"}))
    stated_taxable_value = money_input("Taxable value stated (₹)")
    stated_tax_value = money_input("Tax stated (₹)")
    stated_total_value = money_input("Invoice total stated (₹)")
    notes = forms.CharField(label="Notes", required=False, widget=forms.Textarea(attrs={"rows": 2}))


class InvoiceLineForm(forms.Form):
    description = forms.CharField(label="Description on the invoice", max_length=200)
    item = forms.ModelChoiceField(label="Item", queryset=Item.objects.filter(is_active=True), required=False)
    purity = forms.ModelChoiceField(label="Purity", queryset=Purity.objects.filter(is_active=True), required=False)
    hsn_code = forms.CharField(label="HSN", max_length=12, required=False)
    stated_pieces = pieces_input("Pieces stated")
    stated_gross_weight = weight_input("Weight stated")
    stated_net_weight = weight_input("Net weight stated")
    stated_value = money_input("Value stated (₹)")

    def to_input(self) -> InvoiceLineInput:
        data = self.cleaned_data
        return InvoiceLineInput(
            description=data["description"],
            item_id=data["item"].pk if data.get("item") else None,
            purity_id=data["purity"].pk if data.get("purity") else None,
            hsn_code=data.get("hsn_code", ""),
            stated_pieces=data.get("stated_pieces"),
            stated_gross_weight=data.get("stated_gross_weight"),
            stated_net_weight=data.get("stated_net_weight"),
            stated_value=data.get("stated_value"),
        )


InvoiceLineFormSet = formset_factory(InvoiceLineForm, extra=1, can_delete=True)


def build_input(header: InvoiceHeaderForm, formset) -> InvoiceInput:
    data = header.cleaned_data
    lines = tuple(
        form.to_input()
        for form in formset.forms
        if form.has_changed() and form.cleaned_data and not form.cleaned_data.get("DELETE")
    )
    return InvoiceInput(
        supplier_id=data["supplier"].pk,
        invoice_number=data["invoice_number"],
        invoice_date=data["invoice_date"],
        stated_taxable_value=data.get("stated_taxable_value"),
        stated_tax_value=data.get("stated_tax_value"),
        stated_total_value=data.get("stated_total_value"),
        notes=data.get("notes", ""),
        lines=lines,
    )


class RemoveMatchForm(forms.Form):
    reason = forms.CharField(
        label="Reason for removing this link",
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Required. It is kept in the history.",
    )
