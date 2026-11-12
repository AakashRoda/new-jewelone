"""T01 (C02): receive goods, then enter and match their supplier invoice; repeat matching.

Expected: the physical receipt happens once; invoice entry and matching add no
physical stock.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from core.errors import InvalidState
from demo import fixtures
from inventory import queries, services as inventory
from inventory.models import Inward, StockMovement
from purchasing import services as purchasing
from purchasing.models import InvoiceMatch
from purchasing.services import InvoiceInput, InvoiceLineInput
from tests.conftest import key, ledger_state


def test_t01_receipt_happens_once_and_invoice_adds_no_stock(world):
    m, u = world.m, world.u
    inward = fixtures.t02_chain_receipt(m, u, prefix="t01-receipt")
    after_receipt = ledger_state()
    assert after_receipt["movement_rows"] == 1
    assert after_receipt["totals"] == [
        {
            "stock_mode": "taggable",
            "item": "Chain",
            "unit": "g",
            "pieces": 20,
            "gross_weight": D("200.0000"),
            "net_weight": D("200.0000"),
        }
    ]

    invoice = purchasing.record_supplier_invoice(
        actor=u.accounts,
        data=InvoiceInput(
            supplier_id=m.supplier_a.pk,
            invoice_number="SA/INV/T01",
            invoice_date=date(2026, 11, 11),
            stated_total_value=D("1400000.00"),
            lines=(
                InvoiceLineInput(
                    description="22K gold chains",
                    item_id=m.chain.pk,
                    purity_id=m.gold_22k.pk,
                    stated_pieces=20,
                    stated_gross_weight=D("200.000"),
                    stated_value=D("1400000.00"),
                ),
            ),
        ),
        retry_key=key(),
    )
    assert ledger_state() == after_receipt, "entering the invoice must not touch physical stock"

    invoice_line = invoice.lines.get()
    inward_line = inward.lines.get()
    first = purchasing.match_invoice_line(
        actor=u.accounts, invoice_line_id=invoice_line.pk, inward_line_id=inward_line.pk, retry_key=key()
    )
    assert ledger_state() == after_receipt, "matching the invoice must not touch physical stock"

    # Repeat matching: a fresh request for the same pair, as a second click on a reloaded page would send.
    again = purchasing.match_invoice_line(
        actor=u.accounts, invoice_line_id=invoice_line.pk, inward_line_id=inward_line.pk, retry_key=key()
    )
    assert again.pk == first.pk
    assert InvoiceMatch.objects.filter(removed_at__isnull=True).count() == 1
    assert ledger_state() == after_receipt

    assert [line.pk for line in queries.received_awaiting_lots()] == [inward_line.pk]


def test_t01_retrying_the_same_confirmation_does_not_receive_twice(world):
    m, u = world.m, world.u
    draft = fixtures.draft_karigar_inward(m, u, prefix="t01-retry")
    retry_key = key()
    first = inventory.confirm_inward(
        actor=u.receiver, inward_id=draft.pk, expected_version=draft.version, retry_key=retry_key
    )
    state = ledger_state()

    # Same key, same details: the original result comes back and nothing is added.
    second = inventory.confirm_inward(
        actor=u.receiver, inward_id=draft.pk, expected_version=draft.version, retry_key=retry_key
    )
    assert second.pk == first.pk and second.version == first.version
    assert ledger_state() == state

    # A brand new request to receive it again is refused.
    with pytest.raises(InvalidState, match="already been received"):
        inventory.confirm_inward(
            actor=u.receiver, inward_id=draft.pk, expected_version=first.version, retry_key=key()
        )
    assert ledger_state() == state
    assert StockMovement.objects.filter(inward_line__inward=draft, kind=StockMovement.INWARD_RECEIPT).count() == 1


def test_t01_invoice_is_not_needed_for_receipt_and_can_come_first(world):
    m, u = world.m, world.u
    # Invoice entered before any goods arrive: still no stock.
    purchasing.record_supplier_invoice(
        actor=u.accounts,
        data=InvoiceInput(
            supplier_id=m.supplier_a.pk,
            invoice_number="SA/INV/EARLY",
            invoice_date=date(2026, 11, 1),
            lines=(InvoiceLineInput(description="Chains", stated_gross_weight=D("200.000")),),
        ),
        retry_key=key(),
    )
    assert ledger_state()["movement_rows"] == 0
    # Goods received with no invoice link at all.
    inward = fixtures.t02_chain_receipt(m, u, prefix="t01-noinv")
    assert inward.status == Inward.CONFIRMED
    assert ledger_state()["movement_rows"] == 1


def test_t01_draft_receipt_cannot_be_matched(world):
    m, u = world.m, world.u
    scenario = fixtures.t01_receipt_then_invoice(m, u, prefix="t01-base")
    draft = inventory.create_inward(
        actor=u.receiver,
        data=inventory.InwardInput(
            source_type=Inward.SUPPLIER_PURCHASE,
            stock_mode="taggable",
            supplier_id=m.supplier_a.pk,
            location_id=m.receiving.pk,
            lines=(
                inventory.InwardLineInput(
                    item_id=m.chain.pk,
                    purity_id=m.gold_22k.pk,
                    actual_pieces=1,
                    actual_gross_weight=D("10"),
                    actual_net_weight=D("10"),
                ),
            ),
        ),
        retry_key=key(),
    )
    with pytest.raises(InvalidState, match="not been received"):
        purchasing.match_invoice_line(
            actor=u.accounts,
            invoice_line_id=scenario.invoice.lines.get().pk,
            inward_line_id=draft.lines.get().pk,
            retry_key=key(),
        )
