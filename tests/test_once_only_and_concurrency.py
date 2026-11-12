"""Invariant 1 and the retry-key contract: a receipt is applied once, even after
retries, double-clicks or simultaneous requests. (Stage B1 share of T22.)"""

import threading
from datetime import date
from decimal import Decimal as D

import pytest
from django.db import connections

from core.errors import DomainError, InvalidState, RetryKeyConflict, StaleVersion, ValidationFailed
from demo import fixtures
from inventory import services as inventory
from inventory.models import Inward, StockMovement
from purchasing import services as purchasing
from purchasing.models import InvoiceMatch
from purchasing.services import InvoiceInput, InvoiceLineInput
from tests.conftest import key


def run_together(calls):
    """Start every call at the same instant on its own database connection."""
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)

    def worker(index, call):
        try:
            barrier.wait(timeout=10)
            results[index] = call()
        except DomainError as exc:
            results[index] = exc
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(i, call)) for i, call in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    return results


def gold_balls_input(m, weight="100.000"):
    return inventory.InwardInput(
        source_type=Inward.SUPPLIER_APPROVAL,
        stock_mode="weight_only",
        supplier_id=m.supplier_b.pk,
        location_id=m.safe.pk,
        lines=(
            inventory.InwardLineInput(
                item_id=m.gold_balls.pk, purity_id=m.gold_22k.pk, actual_gross_weight=D(weight)
            ),
        ),
    )


@pytest.mark.django_db(transaction=True)
def test_many_simultaneous_confirmations_receive_the_goods_once(tworld):
    m, u = tworld.m, tworld.u
    draft = inventory.create_inward(actor=u.receiver, data=gold_balls_input(m), retry_key=key())

    results = run_together(
        [
            lambda: inventory.confirm_inward(
                actor=u.verifier, inward_id=draft.pk, expected_version=draft.version, retry_key=key()
            )
            for _ in range(8)
        ]
    )
    succeeded = [r for r in results if isinstance(r, Inward)]
    refused = [r for r in results if isinstance(r, (InvalidState, StaleVersion))]
    assert len(succeeded) == 1 and len(refused) == 7, results
    assert StockMovement.objects.count() == 1
    assert StockMovement.objects.get().gross_weight == D("100.0000")


@pytest.mark.django_db(transaction=True)
def test_double_click_with_the_same_retry_key_returns_one_result(tworld):
    m, u = tworld.m, tworld.u
    draft = inventory.create_inward(actor=u.receiver, data=gold_balls_input(m), retry_key=key())
    shared_key = key()

    results = run_together(
        [
            lambda: inventory.confirm_inward(
                actor=u.verifier, inward_id=draft.pk, expected_version=draft.version, retry_key=shared_key
            )
            for _ in range(6)
        ]
    )
    assert all(isinstance(r, Inward) and r.pk == draft.pk for r in results), results
    assert StockMovement.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_double_submitted_new_inward_creates_one_inward(tworld):
    m, u = tworld.m, tworld.u
    shared_key = key()
    results = run_together(
        [lambda: inventory.create_inward(actor=u.receiver, data=gold_balls_input(m), retry_key=shared_key)] * 5
    )
    assert len({r.pk for r in results}) == 1
    assert Inward.objects.count() == 1


def test_a_retry_key_cannot_be_reused_for_different_details(world):
    m, u = world.m, world.u
    shared_key = key()
    inventory.create_inward(actor=u.receiver, data=gold_balls_input(m, "100.000"), retry_key=shared_key)
    with pytest.raises(RetryKeyConflict):
        inventory.create_inward(actor=u.receiver, data=gold_balls_input(m, "90.000"), retry_key=shared_key)
    # Same details written differently (100 and 100.000) are the same request.
    inventory.create_inward(actor=u.receiver, data=gold_balls_input(m, "100"), retry_key=shared_key)
    assert Inward.objects.count() == 1


def test_a_failed_request_releases_its_retry_key(world):
    m, u = world.m, world.u
    shared_key = key()
    with pytest.raises(ValidationFailed):
        inventory.create_inward(actor=u.receiver, data=gold_balls_input(m, "0"), retry_key=shared_key)
    # The failed attempt stored nothing, so the corrected form can reuse its key.
    inventory.create_inward(actor=u.receiver, data=gold_balls_input(m, "100"), retry_key=shared_key)
    assert Inward.objects.count() == 1


def test_stock_changing_commands_need_a_retry_key(world):
    m, u = world.m, world.u
    with pytest.raises(ValidationFailed, match="retry key"):
        inventory.create_inward(actor=u.receiver, data=gold_balls_input(m), retry_key="")


@pytest.mark.django_db(transaction=True)
def test_simultaneous_matching_creates_one_link(tworld):
    m, u = tworld.m, tworld.u
    inward = fixtures.t02_chain_receipt(m, u, prefix="race-match")
    invoice = purchasing.record_supplier_invoice(
        actor=u.accounts,
        data=InvoiceInput(
            supplier_id=m.supplier_a.pk,
            invoice_number="SA/INV/RACE",
            invoice_date=date(2026, 11, 11),
            lines=(InvoiceLineInput(description="Chains", stated_gross_weight=D("200")),),
        ),
        retry_key=key(),
    )
    invoice_line_id, inward_line_id = invoice.lines.get().pk, inward.lines.get().pk
    results = run_together(
        [
            lambda: purchasing.match_invoice_line(
                actor=u.accounts, invoice_line_id=invoice_line_id, inward_line_id=inward_line_id, retry_key=key()
            )
            for _ in range(6)
        ]
    )
    assert len({r.pk for r in results}) == 1, results
    assert InvoiceMatch.objects.count() == 1
    assert StockMovement.objects.count() == 1
