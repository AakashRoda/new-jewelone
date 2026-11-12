"""Read-only views of stock, all derived from recorded receipts and movements."""

from django.db.models import Sum

from masters.models import Item

from .models import Inward, InwardLine, StockMovement


def weight_only_balances() -> list[dict]:
    """Current weight-only stock per item, purity, variety and location.

    A projection of the movement ledger; there is no stored, editable total.
    """
    rows = (
        StockMovement.objects.filter(stock_mode=Item.WEIGHT_ONLY)
        .values(
            "item_id", "item__name", "purity__name", "variety__name", "unit__code", "location__name"
        )
        .annotate(weight=Sum("gross_weight"))
        .order_by("item__name", "purity__name", "variety__name", "location__name")
    )
    return [
        {
            "item": row["item__name"],
            "purity": row["purity__name"],
            "variety": row["variety__name"],
            "unit": row["unit__code"],
            "location": row["location__name"],
            "weight": row["weight"],
        }
        for row in rows
        if row["weight"] != 0
    ]


def received_awaiting_lots():
    """Tagged-piece receipts that are in stock but not yet split into lots.

    Lot creation arrives in stage B2; until then every received tagged-piece
    line is still wholly unallocated.
    """
    return (
        InwardLine.objects.filter(
            inward__status=Inward.CONFIRMED, inward__stock_mode=Item.TAGGABLE, is_removed=False
        )
        .select_related("inward", "inward__supplier", "inward__karigar", "inward__location", "item", "purity", "variety", "unit")
        .order_by("item__name", "inward_id", "line_no")
    )


def physical_totals() -> list[dict]:
    """Store-wide physical stock by stock mode, item and unit, from the ledger."""
    rows = (
        StockMovement.objects.values("stock_mode", "item__name", "unit__code")
        .annotate(pieces=Sum("pieces"), gross=Sum("gross_weight"), net=Sum("net_weight"))
        .order_by("stock_mode", "item__name")
    )
    return [
        {
            "stock_mode": row["stock_mode"],
            "item": row["item__name"],
            "unit": row["unit__code"],
            "pieces": row["pieces"],
            "gross_weight": row["gross"],
            "net_weight": row["net"],
        }
        for row in rows
    ]
