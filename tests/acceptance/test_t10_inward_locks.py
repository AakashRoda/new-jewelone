"""T10 (C02, C11): authorised edits before and after the lock; direct-weight lock.

Expected: pre-lock edits need a reason. A direct-weight confirmation locks its
inward. There is no ordinary edit bypass.

"First lot locks a taggable inward immediately" needs the CreateLot command of
stage B2. What is checked here is the lock that CreateLot will apply
(``apply_first_lot_lock``) and that editing honours it.
"""

import threading
from decimal import Decimal as D

import pytest
from django.db import connections, transaction

from audit.models import AuditEvent
from core.errors import CapabilityDenied, DomainError, InwardLocked, StaleVersion, ValidationFailed
from demo import fixtures
from inventory import services as inventory
from inventory.models import Inward, StockMovement
from tests.conftest import key, ledger_state, weight_only_balance


def as_input(inward: Inward, **line_changes) -> inventory.InwardInput:
    """The inward's current details as an edit request, with changes to its first line."""
    lines = []
    for index, line in enumerate(inward.lines.filter(is_removed=False).order_by("line_no")):
        fields = dict(
            id=line.pk,
            item_id=line.item_id,
            purity_id=line.purity_id,
            variety_id=line.variety_id,
            declared_pieces=line.declared_pieces,
            declared_gross_weight=line.declared_gross_weight,
            declared_net_weight=line.declared_net_weight,
            actual_pieces=line.actual_pieces,
            actual_gross_weight=line.actual_gross_weight,
            actual_net_weight=line.actual_net_weight,
            condition_notes=line.condition_notes,
        )
        if index == 0:
            fields.update(line_changes)
        lines.append(inventory.InwardLineInput(**fields))
    return inventory.InwardInput(
        source_type=inward.source_type,
        stock_mode=inward.stock_mode,
        supplier_id=inward.supplier_id,
        karigar_id=inward.karigar_id,
        source_reference=inward.source_reference,
        source_date=inward.source_date,
        location_id=inward.location_id,
        custodian_id=inward.custodian_id,
        notes=inward.notes,
        lines=tuple(lines),
    )


def edit(actor, inward, data, reason, version=None):
    return inventory.edit_inward(
        actor=actor,
        inward_id=inward.pk,
        data=data,
        reason=reason,
        expected_version=inward.version if version is None else version,
        retry_key=key(),
    )


def test_t10_pre_lock_edit_needs_a_reason(world):
    m, u = world.m, world.u
    draft = fixtures.draft_karigar_inward(m, u, prefix="t10")
    changed = as_input(draft, actual_gross_weight=D("49.960"), actual_net_weight=D("49.960"))

    for missing in ("", "   ", "ok"):
        with pytest.raises(ValidationFailed, match="reason"):
            edit(u.receiver, draft, changed, missing)
    draft.refresh_from_db()
    assert draft.lines.get().actual_gross_weight == D("49.9500"), "a refused edit changes nothing"

    edited = edit(u.receiver, draft, changed, "Re-weighed on the calibrated scale")
    assert edited.lines.get().actual_gross_weight == D("49.9600")
    assert edited.version == draft.version + 1

    event = AuditEvent.objects.filter(action="inward.edit", outcome="succeeded").get()
    assert event.reason == "Re-weighed on the calibrated scale"
    assert event.actor == u.receiver and event.capability == "inward.edit"
    assert event.payload["before"]["lines"][0]["actual_gross_weight"] == "49.9500"
    assert event.payload["after"]["lines"][0]["actual_gross_weight"] == "49.9600"


def test_t10_edit_right_comes_from_permission_not_from_being_the_creator(world):
    m, u = world.m, world.u
    draft = fixtures.draft_karigar_inward(m, u, prefix="t10")  # created by demo_receiver
    changed = as_input(draft, condition_notes="Checked by another person")

    # A different user who holds inward.edit may edit it.
    edit(u.verifier, draft, changed, "Second check of the karigar slip")

    # The creator loses the right as soon as the role no longer grants it.
    role = u.receiver.roles.get()
    role.capabilities.remove(role.capabilities.get(key="inward.edit"))
    draft.refresh_from_db()
    with pytest.raises(CapabilityDenied):
        edit(u.receiver, draft, changed, "Trying again without the permission")
    denied = AuditEvent.objects.filter(action="inward.edit", outcome="denied").get()
    assert denied.actor == u.receiver and denied.capability == "inward.edit"
    assert denied.target_id == draft.pk


def test_t10_direct_weight_confirmation_locks_the_inward(world):
    m, u = world.m, world.u
    inward = fixtures.t08_gold_balls_on_approval(m, u, prefix="t10")
    assert inward.is_locked and inward.lock_cause == Inward.LOCK_DIRECT_WEIGHT
    before = ledger_state()

    # Every demo user is refused, including the one holding every capability:
    # there is no ordinary edit that gets past the lock.
    for actor in (u.owner, u.verifier):
        with pytest.raises(InwardLocked, match="O01"):
            edit(actor, inward, as_input(inward, actual_gross_weight=D("99.000")), "Trying to change a locked receipt")
    inward.refresh_from_db()
    assert inward.lines.get().actual_gross_weight == D("100.0000")
    assert ledger_state() == before
    assert weight_only_balance(m.gold_balls) == D("100.0000")


def test_t10_taggable_inward_stays_editable_after_receipt_until_its_first_lot(world):
    m, u = world.m, world.u
    inward = fixtures.t01_receipt_then_invoice(m, u, prefix="t10").inward
    assert inward.status == Inward.CONFIRMED and not inward.is_locked

    # Received but no lot yet: an authorised edit with a reason is allowed and
    # physical stock follows the corrected weight without rewriting history.
    edited = edit(
        u.verifier,
        inward,
        as_input(inward, actual_gross_weight=D("99.500"), actual_net_weight=D("99.500")),
        "Scale reading corrected before lot creation",
    )
    movements = list(StockMovement.objects.filter(inward_line__inward=inward).order_by("id"))
    assert [(mv.kind, mv.gross_weight) for mv in movements] == [
        (StockMovement.INWARD_RECEIPT, D("100.0000")),
        (StockMovement.INWARD_EDIT_ADJUSTMENT, D("-0.5000")),
    ]
    assert ledger_state()["totals"][0]["gross_weight"] == D("99.5000")

    # Stage B2's CreateLot applies this lock in its own transaction.
    with transaction.atomic():
        locked_row = Inward.objects.select_for_update().get(pk=inward.pk)
        inventory.apply_first_lot_lock(locked_row, actor=u.owner, retry_key=key())

    edited.refresh_from_db()
    assert edited.is_locked and edited.lock_cause == Inward.LOCK_FIRST_LOT
    state = ledger_state()
    with pytest.raises(InwardLocked, match="first lot"):
        edit(u.owner, edited, as_input(edited, actual_gross_weight=D("98.000"), actual_net_weight=D("98.000")), "After the lot exists")
    assert ledger_state() == state


def test_t10_no_unlock_and_no_superuser_bypass(world):
    m, u = world.m, world.u
    inward = fixtures.t08_gold_balls_on_approval(m, u, prefix="t10")

    assert not [name for name in dir(inventory) if "unlock" in name.lower()], "no unlock command exists"

    # Django's superuser flag grants nothing here.
    from accounts.models import User

    root = User.objects.create_user("root_without_roles", password="x" * 12, is_superuser=True, is_staff=True)
    assert root.capability_keys() == set()
    with pytest.raises(CapabilityDenied):
        edit(root, inward, as_input(inward, actual_gross_weight=D("1.000")), "Superuser attempt")
    inward.refresh_from_db()
    assert inward.is_locked and inward.lines.get().actual_gross_weight == D("100.0000")


def test_t10_edit_from_a_stale_screen_is_refused(world):
    m, u = world.m, world.u
    draft = fixtures.draft_karigar_inward(m, u, prefix="t10")
    stale_version = draft.version
    edit(u.receiver, draft, as_input(draft, condition_notes="First change"), "First change saved")
    with pytest.raises(StaleVersion):
        edit(u.verifier, draft, as_input(draft, condition_notes="Second change"), "Based on the old screen", version=stale_version)


@pytest.mark.django_db(transaction=True)
def test_t10_lock_is_rechecked_when_an_edit_and_a_confirmation_collide(tworld):
    """Invariant 7: an edit racing with the action that locks cannot slip past the lock."""
    m, u = tworld.m, tworld.u
    for round_no in range(6):
        prefix = f"t10-race-{round_no}"
        draft = inventory.create_inward(
            actor=u.receiver,
            data=inventory.InwardInput(
                source_type=Inward.SUPPLIER_APPROVAL,
                stock_mode="weight_only",
                supplier_id=m.supplier_b.pk,
                location_id=m.safe.pk,
                lines=(
                    inventory.InwardLineInput(
                        item_id=m.gold_balls.pk, purity_id=m.gold_22k.pk, actual_gross_weight=D("100.000")
                    ),
                ),
            ),
            retry_key=f"{prefix}-create",
        )
        edited_input = as_input(draft, actual_gross_weight=D("90.000"))
        outcomes: dict[str, object] = {}
        barrier = threading.Barrier(2)

        def run(name, call):
            try:
                barrier.wait(timeout=10)
                call()
                outcomes[name] = "ok"
            except DomainError as exc:
                outcomes[name] = exc
            finally:
                connections.close_all()

        threads = [
            threading.Thread(
                target=run,
                args=(
                    "confirm",
                    lambda: inventory.confirm_inward(
                        actor=u.verifier, inward_id=draft.pk, expected_version=draft.version, retry_key=key()
                    ),
                ),
            ),
            threading.Thread(
                target=run,
                args=("edit", lambda: edit(u.receiver, draft, edited_input, "Racing edit of the draft")),
            ),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        final = Inward.objects.get(pk=draft.pk)
        ledger = sum(
            (mv.gross_weight for mv in StockMovement.objects.filter(inward_line__inward=final)), D("0")
        )
        line_weight = final.lines.get().actual_gross_weight
        if outcomes["confirm"] == "ok":
            # Confirmation won: the edit must have been refused and stock equals what was confirmed.
            assert isinstance(outcomes["edit"], (InwardLocked, StaleVersion)), outcomes
            assert final.is_locked and line_weight == D("100.0000") and ledger == D("100.0000")
        else:
            # The edit won: the confirmation was working from an old screen and is refused.
            assert outcomes["edit"] == "ok" and isinstance(outcomes["confirm"], StaleVersion), outcomes
            assert not final.is_locked and line_weight == D("90.0000") and ledger == D("0")
