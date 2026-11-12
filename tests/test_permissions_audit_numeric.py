"""Server-side permission checks, append-only history and exact arithmetic."""

from decimal import Decimal as D

import pytest
from django.db import IntegrityError, transaction

from audit.models import AuditEvent
from core import numeric
from core.errors import CapabilityDenied
from core.idempotency import payload_hash
from demo import fixtures
from inventory import services as inventory
from inventory.models import Inward, InwardLine, StockMovement
from purchasing import models as purchasing_models
from purchasing import services as purchasing
from tests.conftest import key, ledger_state


# ---- permissions ---------------------------------------------------------

def test_only_someone_allowed_to_open_parcels_can_confirm_a_supplier_receipt(world):
    m, u = world.m, world.u
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
                    actual_pieces=10,
                    actual_gross_weight=D("100"),
                    actual_net_weight=D("100"),
                ),
            ),
        ),
        retry_key=key(),
    )
    # The receiving clerk entered it but may not open and verify supplier parcels.
    with pytest.raises(CapabilityDenied) as denied:
        inventory.confirm_inward(actor=u.receiver, inward_id=draft.pk, expected_version=1, retry_key=key())
    assert denied.value.capability == "parcel.open"
    assert StockMovement.objects.count() == 0
    assert AuditEvent.objects.filter(action="inward.confirm", outcome="denied", capability="parcel.open").count() == 1

    confirmed = inventory.confirm_inward(actor=u.verifier, inward_id=draft.pk, expected_version=1, retry_key=key())
    assert confirmed.confirmed_by == u.verifier and confirmed.created_by == u.receiver
    assert StockMovement.objects.get().actor == u.verifier


def test_users_without_the_capability_are_refused_and_the_refusal_is_recorded(world):
    m, u = world.m, world.u
    scenario = fixtures.t01_receipt_then_invoice(m, u, prefix="perm")
    before = ledger_state()

    with pytest.raises(CapabilityDenied):
        inventory.create_inward(actor=u.viewer, data=None, retry_key=key())
    with pytest.raises(CapabilityDenied):
        purchasing.record_supplier_invoice(actor=u.receiver, data=None, retry_key=key())
    with pytest.raises(CapabilityDenied):
        purchasing.match_invoice_line(
            actor=u.verifier,
            invoice_line_id=scenario.invoice.lines.get().pk,
            inward_line_id=scenario.inward.lines.get().pk,
            retry_key=key(),
        )
    assert ledger_state() == before
    assert AuditEvent.objects.filter(outcome="denied").count() == 3


def test_capabilities_are_read_at_action_time(world):
    u = world.u
    assert u.viewer.capability_keys() == set()
    role = u.viewer.roles.get()
    from accounts.models import Capability

    role.capabilities.add(Capability.objects.get(key="inward.create"))
    assert u.viewer.has_capability("inward.create")  # same user object, no stale cache
    u.viewer.is_active = False
    assert u.viewer.capability_keys() == set()


# ---- audit and history ---------------------------------------------------

def test_every_stock_mutation_names_its_actor_and_source(world):
    m, u = world.m, world.u
    fixtures.t01_receipt_then_invoice(m, u, prefix="aud")
    movement = StockMovement.objects.get()
    assert movement.actor == u.verifier
    assert movement.source_command == "ConfirmInward" and movement.retry_key == "aud-confirm"
    actions = list(AuditEvent.objects.order_by("id").values_list("action", "actor__username"))
    assert actions == [
        ("inward.create", "demo_receiver"),
        ("inward.confirm", "demo_verifier"),
        ("purchase_invoice.record", "demo_accounts"),
        ("purchase_invoice.match", "demo_accounts"),
    ]


def test_history_tables_refuse_update_and_delete(world):
    m, u = world.m, world.u
    fixtures.t08_gold_balls_on_approval(m, u, prefix="hist")
    for queryset in (StockMovement.objects.all(), AuditEvent.objects.all()):
        with pytest.raises(IntegrityError, match="append-only"), transaction.atomic():
            queryset.update(retry_key="tampered")
        with pytest.raises(IntegrityError, match="append-only"), transaction.atomic():
            queryset.delete()
    assert StockMovement.objects.get().gross_weight == D("100.0000")


def test_removing_a_wrong_invoice_link_keeps_its_history(world):
    m, u = world.m, world.u
    scenario = fixtures.t01_receipt_then_invoice(m, u, prefix="unmatch")
    before = ledger_state()
    removed = purchasing.remove_invoice_match(
        actor=u.accounts, match_id=scenario.match.pk, reason="Linked to the wrong receipt", retry_key=key()
    )
    assert removed.removed_by == u.accounts and removed.removal_reason == "Linked to the wrong receipt"
    assert purchasing_models.InvoiceMatch.objects.count() == 1, "the link row is kept, not deleted"
    assert ledger_state() == before
    # It can be linked again afterwards.
    again = purchasing.match_invoice_line(
        actor=u.accounts,
        invoice_line_id=scenario.invoice.lines.get().pk,
        inward_line_id=scenario.inward.lines.get().pk,
        retry_key=key(),
    )
    assert again.pk != removed.pk


# ---- database-level guards ----------------------------------------------

def test_database_refuses_impossible_receipt_lines(world):
    m, u = world.m, world.u
    inward = fixtures.draft_karigar_inward(m, u, prefix="db")
    base = dict(inward=inward, item=m.bangle, purity=m.gold_22k, unit=m.g)
    with pytest.raises(IntegrityError), transaction.atomic():
        InwardLine.objects.create(line_no=50, actual_gross_weight=D("0"), **base)
    with pytest.raises(IntegrityError), transaction.atomic():
        InwardLine.objects.create(line_no=51, actual_gross_weight=D("10"), actual_net_weight=D("10.0001"), **base)


def test_database_refuses_a_second_receipt_movement_for_the_same_line(world):
    m, u = world.m, world.u
    inward = fixtures.t08_gold_balls_on_approval(m, u, prefix="db2")
    line = inward.lines.get()
    with pytest.raises(IntegrityError), transaction.atomic():
        StockMovement.objects.create(
            kind=StockMovement.INWARD_RECEIPT,
            stock_mode="weight_only",
            inward_line=line,
            item=line.item,
            purity=line.purity,
            unit=line.unit,
            location=inward.location,
            gross_weight=D("100"),
            actor=u.owner,
            source_command="test",
            retry_key="test-duplicate",
        )


def test_database_refuses_a_confirmed_weight_only_inward_that_is_not_locked(world):
    m, u = world.m, world.u
    inward = fixtures.t08_gold_balls_on_approval(m, u, prefix="db3")
    with pytest.raises(IntegrityError), transaction.atomic():
        Inward.objects.filter(pk=inward.pk).update(locked_at=None, lock_cause="")


# ---- numbers -------------------------------------------------------------

def test_weights_are_exact_decimals():
    assert numeric.to_decimal("0.010", places=4, what="w") == D("0.0100")  # 10 mg
    assert numeric.carats_to_grams(D("1")) == D("0.2")  # 1 ct = 0.200 g
    assert numeric.carats_to_grams(D("4")) == D("0.8")
    assert numeric.carats_to_grams(D("0.001")) == D("0.0002")
    assert sum([D("0.1")] * 3, D("0")) == D("0.3")
    with pytest.raises(ValueError, match="floating"):
        numeric.to_decimal(0.1, places=4, what="w")
    with pytest.raises(ValueError, match="decimal places"):
        numeric.to_decimal("1.00001", places=4, what="w")  # refused, not rounded
    with pytest.raises(ValueError):
        numeric.to_decimal("NaN", places=4, what="w")
    assert payload_hash({"w": D("100")}) == payload_hash({"w": D("100.000")})
    with pytest.raises(TypeError):
        payload_hash({"w": 0.1})


def test_no_purchase_metal_rate_or_metal_cost_field_exists():
    """C06: purchase metal-rate tracking and metal purchase-cost valuation are excluded."""
    from django.apps import apps

    banned = ("metal_rate", "purchase_rate", "metal_cost", "purchase_cost", "acquisition_cost", "margin")
    offenders = [
        f"{model.__name__}.{field.name}"
        for model in apps.get_models()
        for field in model._meta.get_fields()
        if any(word in field.name for word in banned)
    ]
    assert offenders == []


def test_declared_versus_actual_difference_is_kept_and_unstated_is_not_zero(world):
    m, u = world.m, world.u
    line = fixtures.draft_karigar_inward(m, u, prefix="diff").lines.get()
    assert line.gross_difference == D("-0.0500") and line.pieces_difference == 0
    unstated = fixtures.t08_gold_balls_on_approval(m, u, prefix="diff2").lines.get()
    unstated.declared_gross_weight = None
    assert unstated.gross_difference is None
