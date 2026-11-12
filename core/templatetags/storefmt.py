"""Display formatting for weights and money. Formatting only; stored values are never rounded."""

from decimal import Decimal

from django import template

register = template.Library()

DASH = "—"


def _plain_weight(value: Decimal) -> str:
    thousandths = value.quantize(Decimal("0.001"))
    if thousandths == value:
        return f"{thousandths:.3f}"
    return f"{value:.4f}"


@register.filter
def weight(value):
    """100.000 for normal values; a fourth decimal is shown only when it is not zero."""
    if value is None or value == "":
        return DASH
    return _plain_weight(Decimal(value))


@register.filter
def signed_weight(value):
    if value is None or value == "":
        return DASH
    value = Decimal(value)
    if value == 0:
        return _plain_weight(value)
    return ("+" if value > 0 else "−") + _plain_weight(abs(value))


@register.filter
def signed_int(value):
    if value is None or value == "":
        return DASH
    return f"{value:+d}".replace("-", "−") if value else "0"


@register.filter
def rupees(value):
    """Indian digit grouping: 7,00,000.00."""
    if value is None or value == "":
        return DASH
    value = Decimal(value).quantize(Decimal("0.01"))
    whole, _, fraction = f"{abs(value):.2f}".partition(".")
    head, tail = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    grouped = ",".join(groups + [tail]) if groups else tail
    return f"{'−' if value < 0 else ''}₹{grouped}.{fraction}"


@register.filter
def dash(value):
    return DASH if value is None or value == "" else value
