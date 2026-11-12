"""T08 (C04, C07), direct-weight parts that belong to stage B1.

Receive 100 g of untaggable gold balls; later match the invoice for the
retained 50 g. Expected here: stock from the receipt is by weight only, with no
lots, tags or counts, and the invoice adds nothing.

The 50 g approval return in the middle of T08 is a supplier return dispatch.
It belongs to stage B3 and is not claimed here.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from core.errors import ValidationFailed
from demo import fixtures
from inventory import services as inventory
from inventory.models import Inward, StockMovement
from purchasing import services as purchasing
from purchasing.services import InvoiceInput, InvoiceLineInput
from tests.conftest import key, ledger_state, weight_only_balance


def test_t08_gold_balls_enter_stock_by_weight_only(world):
    m, u = world.m, world.u
    assert weight_only_balance(m.gold_balls) == D("0")

    inward = fixtures.t08_gold_balls_on_approval(m, u, prefix="t08")

    assert weight_only_balance(m.gold_balls) == D("100.0000")
    line = inward.lines.get()
    assert line.actual_pieces is None and line.declared_pieces is None, "no piece count for weight-only stock"
    assert line.actual_net_weight is None
    movement = StockMovement.objects.get()
    assert movement.kind == StockMovement.INWARD_RECEIPT
    assert movement.pieces is None and movement.net_weight is None
    assert movement.gross_weight == D("100.0000")
    # Confirmation is the moment it both enters stock and locks.
    assert inward.status == Inward.CONFIRMED
    assert inward.is_locked and inward.lock_cause == Inward.LOCK_DIRECT_WEIGHT


def test_t08_invoice_for_retained_weight_adds_nothing(world):
    m, u = world.m, world.u
    inward = fixtures.t08_gold_balls_on_approval(m, u, prefix="t08")
    before = ledger_state()

    invoice = purchasing.record_supplier_invoice(
        actor=u.accounts,
        data=InvoiceInput(
            supplier_id=m.supplier_b.pk,
            invoice_number="SB/INV/T08",
            invoice_date=date(2026, 11, 20),
            lines=(
                InvoiceLineInput(
                    description="22K gold balls retained from approval",
                    item_id=m.gold_balls.pk,
                    purity_id=m.gold_22k.pk,
                    stated_gross_weight=D("50.000"),
                ),
            ),
        ),
        retry_key=key(),
    )
    purchasing.match_invoice_line(
        actor=u.accounts,
        invoice_line_id=invoice.lines.get().pk,
        inward_line_id=inward.lines.get().pk,
        retry_key=key(),
    )
    assert ledger_state() == before
    # Until the B3 return is built the whole receipt is still physically held.
    assert weight_only_balance(m.gold_balls) == D("100.0000")
    # The original receipt is preserved exactly.
    assert inward.lines.get().actual_gross_weight == D("100.0000")


def test_t08_weight_only_receipt_refuses_piece_counts_and_tagged_items(world):
    m, u = world.m, world.u

    def attempt(line):
        return inventory.create_inward(
            actor=u.receiver,
            data=inventory.InwardInput(
                source_type=Inward.SUPPLIER_APPROVAL,
                stock_mode="weight_only",
                supplier_id=m.supplier_b.pk,
                location_id=m.safe.pk,
                lines=(line,),
            ),
            retry_key=key(),
        )

    with pytest.raises(ValidationFailed, match="no piece count"):
        attempt(
            inventory.InwardLineInput(
                item_id=m.gold_balls.pk, purity_id=m.gold_22k.pk, actual_gross_weight=D("100"), actual_pieces=40
            )
        )
    # Mixed taggable and weight-only inwards stay unavailable until O01 is decided.
    with pytest.raises(ValidationFailed, match="O01"):
        attempt(
            inventory.InwardLineInput(
                item_id=m.chain.pk, purity_id=m.gold_22k.pk, actual_gross_weight=D("100")
            )
        )
    assert Inward.objects.count() == 0
