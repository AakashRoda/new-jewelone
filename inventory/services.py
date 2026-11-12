"""Business commands for physical receipts: CreateInward, EditInward, ConfirmInward.

Rules enforced here (and again by database constraints where possible):

* A receipt enters physical stock exactly once, on confirmation (C02).
* A weight-only receipt locks when it is confirmed. A tagged-pieces receipt
  locks when its first lot is created (stage B2 calls ``apply_first_lot_lock``).
* Before the lock, an edit needs the inward.edit capability and a reason.
* After the lock there is no direct edit and no unlock (C11). Correction
  posting stays unavailable until O01 is decided.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.utils import timezone

from accounts.permissions import records_denials, require
from audit import services as audit
from core import numeric
from core.errors import InvalidState, InwardLocked, StaleVersion, ValidationFailed
from core.idempotency import run_once
from masters.models import Item, Karigar, Location, Purity, Supplier, Variety

from .models import Inward, InwardLine, StockMovement

ZERO = Decimal("0")


@dataclass(frozen=True)
class InwardLineInput:
    item_id: int
    purity_id: int
    actual_gross_weight: Decimal
    variety_id: int | None = None
    actual_pieces: int | None = None
    actual_net_weight: Decimal | None = None
    declared_pieces: int | None = None
    declared_gross_weight: Decimal | None = None
    declared_net_weight: Decimal | None = None
    condition_notes: str = ""
    id: int | None = None  # existing line when editing


@dataclass(frozen=True)
class InwardInput:
    source_type: str
    stock_mode: str
    location_id: int
    lines: tuple[InwardLineInput, ...]
    supplier_id: int | None = None
    karigar_id: int | None = None
    source_reference: str = ""
    source_date: date | None = None
    custodian_id: int | None = None
    notes: str = ""


# --------------------------------------------------------------------------
# Explanations shown to operators
# --------------------------------------------------------------------------

def lock_explanation(inward: Inward) -> str:
    if not inward.is_locked:
        return ""
    if inward.lock_cause == Inward.LOCK_DIRECT_WEIGHT:
        cause = "this weight-only receipt was confirmed and its weight was added to stock"
    else:
        cause = "its first lot has been created"
    return (
        f"{inward} is locked because {cause}. A locked inward cannot be edited directly. "
        "Changes need a separate correction, and correction posting is not available yet "
        "because the owner has not decided the correction policy (open decision O01)."
    )


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def _weight(value, what: str, errors: list[str]) -> Decimal | None:
    if value is None:
        return None
    try:
        return numeric.to_decimal(value, places=numeric.WEIGHT_DECIMAL_PLACES, what=what)
    except ValueError as exc:
        errors.append(str(exc))
        return None


def _validate(data: InwardInput, existing: Inward | None) -> dict:
    """Check an inward's details. Returns resolved master records and clean lines."""
    errors: list[str] = []

    if data.source_type not in dict(Inward.SOURCE_TYPES):
        errors.append("Choose where the goods came from (supplier purchase, supplier approval memo or karigar).")
    if data.stock_mode not in dict(Item.STOCK_MODES):
        errors.append("Choose whether this inward is for tagged pieces or weight-only stock.")
    if existing is not None and data.stock_mode != existing.stock_mode:
        errors.append(
            "The stock type of an inward cannot be changed after it is created. Enter a separate inward instead."
        )

    supplier = karigar = None
    if data.source_type in Inward.SUPPLIER_SOURCES:
        supplier = Supplier.objects.filter(pk=data.supplier_id).first() if data.supplier_id else None
        if supplier is None:
            errors.append("Choose the supplier the goods came from.")
        elif not supplier.is_active and not (existing and existing.supplier_id == supplier.pk):
            errors.append(f"Supplier {supplier} is inactive and cannot be used on a new receipt.")
        if data.karigar_id:
            errors.append("A supplier receipt cannot also name a karigar.")
    elif data.source_type == Inward.KARIGAR_INWARD:
        karigar = Karigar.objects.filter(pk=data.karigar_id).first() if data.karigar_id else None
        if karigar is None:
            errors.append("Choose the karigar the goods came from.")
        elif not karigar.is_active and not (existing and existing.karigar_id == karigar.pk):
            errors.append(f"Karigar {karigar} is inactive and cannot be used on a new receipt.")
        if data.supplier_id:
            errors.append("A karigar inward cannot also name a supplier.")

    location = Location.objects.filter(pk=data.location_id).first() if data.location_id else None
    if location is None:
        errors.append("Choose the location where the goods are received.")
    elif not location.is_active and not (existing and existing.location_id == location.pk):
        errors.append(f"Location {location} is inactive.")

    custodian = None
    if data.custodian_id:
        from accounts.models import User

        custodian = User.objects.filter(pk=data.custodian_id, is_active=True).first()
        if custodian is None:
            errors.append("The chosen custodian is not an active user.")

    if not data.lines:
        errors.append("Add at least one line with the goods actually received.")

    existing_line_ids = set()
    if existing is not None:
        existing_line_ids = {line.pk for line in existing.lines.all() if not line.is_removed}
    seen_ids: set[int] = set()
    taggable = data.stock_mode == Item.TAGGABLE
    clean_lines = []

    for index, line in enumerate(data.lines, start=1):
        label = f"Line {index}"
        if line.id is not None:
            if line.id not in existing_line_ids or line.id in seen_ids:
                errors.append(f"{label}: this line does not belong to the inward being edited.")
            seen_ids.add(line.id)

        item = Item.objects.select_related("weight_unit").filter(pk=line.item_id).first()
        purity = Purity.objects.filter(pk=line.purity_id).first()
        variety = Variety.objects.filter(pk=line.variety_id).first() if line.variety_id else None
        if item is None:
            errors.append(f"{label}: choose an item.")
            continue
        if purity is None:
            errors.append(f"{label}: choose a purity.")
        if item.stock_mode != data.stock_mode:
            item_kind = "weight-only stock" if item.stock_mode == Item.WEIGHT_ONLY else "tagged-piece stock"
            inward_kind = "tagged pieces" if taggable else "weight-only stock"
            errors.append(
                f"{label}: {item.name} is {item_kind} and cannot go on an inward for {inward_kind}. "
                "Enter it on a separate inward. Mixed inwards are not available until their lock "
                "behaviour is decided (open decision O01)."
            )
        if line.variety_id and (variety is None or variety.item_id != item.pk):
            errors.append(f"{label}: the chosen variety does not belong to {item.name}.")

        unit = item.weight_unit.code
        gross = _weight(line.actual_gross_weight, f"{label} actual weight", errors)
        net = _weight(line.actual_net_weight, f"{label} actual net weight", errors)
        declared_gross = _weight(line.declared_gross_weight, f"{label} declared weight", errors)
        declared_net = _weight(line.declared_net_weight, f"{label} declared net weight", errors)

        if gross is None or gross <= ZERO:
            errors.append(f"{label}: enter the actual received weight (more than 0 {unit}).")
        for what, value in (("declared weight", declared_gross), ("declared net weight", declared_net)):
            if value is not None and value < ZERO:
                errors.append(f"{label}: {what} cannot be negative ({numeric.show(value)} {unit}).")
        for what, value in (("actual pieces", line.actual_pieces), ("declared pieces", line.declared_pieces)):
            if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
                errors.append(f"{label}: {what} must be a whole number.")

        if taggable:
            if not line.actual_pieces or line.actual_pieces < 1:
                errors.append(f"{label}: enter the number of pieces actually received.")
            if net is None or net <= ZERO:
                errors.append(f"{label}: enter the actual net weight (more than 0 {unit}).")
            elif gross is not None and net > gross:
                errors.append(
                    f"{label}: net weight {numeric.show(net)} {unit} cannot be more than "
                    f"gross weight {numeric.show(gross)} {unit}."
                )
        else:
            if line.actual_pieces is not None or line.declared_pieces is not None:
                errors.append(f"{label}: weight-only stock is received by weight and has no piece count.")
            if net is not None or declared_net is not None:
                errors.append(f"{label}: weight-only stock has a single weight, not separate gross and net.")

        clean_lines.append(
            {
                "id": line.id,
                "item": item,
                "purity": purity,
                "variety": variety,
                "unit": item.weight_unit,
                "declared_pieces": line.declared_pieces,
                "declared_gross_weight": declared_gross,
                "declared_net_weight": declared_net,
                "actual_pieces": line.actual_pieces,
                "actual_gross_weight": gross,
                "actual_net_weight": net,
                "condition_notes": (line.condition_notes or "").strip(),
            }
        )

    if errors:
        raise ValidationFailed(errors)
    return {
        "supplier": supplier,
        "karigar": karigar,
        "location": location,
        "custodian": custodian,
        "lines": clean_lines,
    }


# --------------------------------------------------------------------------
# Snapshots for audit history
# --------------------------------------------------------------------------

def snapshot(inward: Inward) -> dict:
    lines = []
    for line in inward.lines.select_related("item", "purity", "variety", "unit").order_by("line_no"):
        lines.append(
            {
                "line_no": line.line_no,
                "item": line.item.name,
                "purity": line.purity.name,
                "variety": line.variety.name if line.variety_id else None,
                "unit": line.unit.code,
                "declared_pieces": line.declared_pieces,
                "declared_gross_weight": line.declared_gross_weight,
                "declared_net_weight": line.declared_net_weight,
                "actual_pieces": line.actual_pieces,
                "actual_gross_weight": line.actual_gross_weight,
                "actual_net_weight": line.actual_net_weight,
                "condition_notes": line.condition_notes,
                "removed": line.is_removed,
            }
        )
    return {
        "number": inward.number,
        "status": inward.status,
        "source_type": inward.source_type,
        "supplier": inward.supplier.name if inward.supplier_id else None,
        "karigar": inward.karigar.name if inward.karigar_id else None,
        "source_reference": inward.source_reference,
        "source_date": inward.source_date,
        "stock_mode": inward.stock_mode,
        "location": inward.location.name,
        "custodian": inward.custodian.label if inward.custodian_id else None,
        "notes": inward.notes,
        "lines": lines,
    }


# --------------------------------------------------------------------------
# Physical stock ledger
# --------------------------------------------------------------------------

def _post_receipt_movements(inward: Inward, *, actor, command: str, retry_key: str) -> int:
    """Bring the ledger in line with a confirmed inward's lines.

    Works on differences: for each line it compares what the ledger already
    holds with what the line now says and appends only the gap. Calling it
    twice therefore posts nothing the second time. Returns rows appended.
    """
    appended = 0
    weight_only = inward.stock_mode == Item.WEIGHT_ONLY
    for line in inward.lines.all():
        posted: dict[tuple, list] = defaultdict(lambda: [0, ZERO, ZERO])
        has_receipt = False
        for movement in line.movements.all():
            has_receipt = True
            key = (movement.item_id, movement.purity_id, movement.variety_id, movement.unit_id, movement.location_id)
            posted[key][0] += movement.pieces or 0
            posted[key][1] += movement.gross_weight
            posted[key][2] += movement.net_weight or ZERO

        wanted_key = None
        if not line.is_removed:
            wanted_key = (line.item_id, line.purity_id, line.variety_id, line.unit_id, inward.location_id)
        for key in sorted(set(posted) | ({wanted_key} if wanted_key else set()), key=repr):
            if key == wanted_key:
                want = (line.actual_pieces or 0, line.actual_gross_weight, line.actual_net_weight or ZERO)
            else:
                want = (0, ZERO, ZERO)
            have = posted.get(key, [0, ZERO, ZERO])
            delta = (want[0] - have[0], want[1] - have[1], want[2] - have[2])
            if delta == (0, ZERO, ZERO):
                continue
            StockMovement.objects.create(
                kind=StockMovement.INWARD_EDIT_ADJUSTMENT if has_receipt else StockMovement.INWARD_RECEIPT,
                stock_mode=inward.stock_mode,
                inward_line=line,
                item_id=key[0],
                purity_id=key[1],
                variety_id=key[2],
                unit_id=key[3],
                location_id=key[4],
                pieces=None if weight_only else delta[0],
                gross_weight=delta[1],
                net_weight=None if weight_only else delta[2],
                actor=actor,
                source_command=command,
                retry_key=retry_key,
            )
            has_receipt = True
            appended += 1
    return appended


def _locked_for_update(inward_id: int) -> Inward:
    inward = Inward.objects.select_for_update().filter(pk=inward_id).first()
    if inward is None:
        raise InvalidState("This inward no longer exists.")
    return inward


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------

@records_denials
def create_inward(*, actor, data: InwardInput, retry_key: str) -> Inward:
    """Save a new inward as a draft. A draft is not yet in stock."""
    require(actor, "inward.create", action="inward.create")

    def action():
        clean = _validate(data, existing=None)
        inward = Inward.objects.create(
            source_type=data.source_type,
            supplier=clean["supplier"],
            karigar=clean["karigar"],
            source_reference=data.source_reference.strip(),
            source_date=data.source_date,
            stock_mode=data.stock_mode,
            location=clean["location"],
            custodian=clean["custodian"],
            notes=data.notes.strip(),
            created_by=actor,
        )
        inward.number = f"INW-{inward.pk:06d}"
        inward.save(update_fields=["number"])
        for line_no, line in enumerate(clean["lines"], start=1):
            fields = {k: v for k, v in line.items() if k != "id"}
            InwardLine.objects.create(inward=inward, line_no=line_no, **fields)
        audit.record(
            actor=actor,
            action="inward.create",
            capability="inward.create",
            target=inward,
            payload={"after": snapshot(inward)},
            retry_key=retry_key,
        )
        return {"inward_id": inward.pk}

    result, _ = run_once(command="CreateInward", retry_key=retry_key, payload=data, actor=actor, action=action)
    return Inward.objects.get(pk=result["inward_id"])


@records_denials
def edit_inward(
    *, actor, inward_id: int, data: InwardInput, reason: str, expected_version: int, retry_key: str
) -> Inward:
    """Edit an inward before its lock. Needs inward.edit and a clear reason."""
    target = Inward.objects.filter(pk=inward_id).first()
    require(actor, "inward.edit", action="inward.edit", target=target)
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise ValidationFailed(["Give a clear reason for this edit (at least a few words). It is kept in the history."])

    def action():
        # The row lock makes the lock check and the save one step: a lot
        # creation or confirmation running at the same moment waits here.
        inward = _locked_for_update(inward_id)
        if inward.is_locked:
            raise InwardLocked(lock_explanation(inward))
        if inward.version != expected_version:
            raise StaleVersion(str(inward))
        clean = _validate(data, existing=inward)
        before = snapshot(inward)

        inward.source_type = data.source_type
        inward.supplier = clean["supplier"]
        inward.karigar = clean["karigar"]
        inward.source_reference = data.source_reference.strip()
        inward.source_date = data.source_date
        inward.location = clean["location"]
        inward.custodian = clean["custodian"]
        inward.notes = data.notes.strip()
        inward.version += 1
        inward.save()

        current = {line.pk: line for line in inward.lines.all() if not line.is_removed}
        kept_ids = {line["id"] for line in clean["lines"] if line["id"] is not None}
        for line_id, line in current.items():
            if line_id in kept_ids:
                continue
            if inward.is_confirmed:
                # Already counted in physical stock: keep the row, take the quantity out below.
                line.is_removed = True
                line.save(update_fields=["is_removed"])
            else:
                line.delete()
        next_no = max([line.line_no for line in inward.lines.all()], default=0) + 1
        for line in clean["lines"]:
            fields = {k: v for k, v in line.items() if k != "id"}
            if line["id"] is not None:
                InwardLine.objects.filter(pk=line["id"]).update(**fields)
            else:
                InwardLine.objects.create(inward=inward, line_no=next_no, **fields)
                next_no += 1

        if inward.is_confirmed:
            _post_receipt_movements(inward, actor=actor, command="EditInward", retry_key=retry_key)
        audit.record(
            actor=actor,
            action="inward.edit",
            capability="inward.edit",
            target=inward,
            reason=reason,
            payload={"before": before, "after": snapshot(inward)},
            retry_key=retry_key,
        )
        return {"inward_id": inward.pk}

    payload = {"inward_id": inward_id, "data": data, "reason": reason, "expected_version": expected_version}
    run_once(command="EditInward", retry_key=retry_key, payload=payload, actor=actor, action=action)
    return Inward.objects.get(pk=inward_id)


@records_denials
def confirm_inward(*, actor, inward_id: int, expected_version: int, retry_key: str) -> Inward:
    """Confirm the physical receipt: the goods enter store stock, once.

    A supplier parcel may only be confirmed by someone allowed to open and
    verify parcels (C02). Weight-only stock is added straight to the item's
    weight balance and the inward locks at this moment.
    """
    target = Inward.objects.filter(pk=inward_id).first()
    require(actor, "inward.create", action="inward.confirm", target=target)

    def action():
        inward = _locked_for_update(inward_id)
        if inward.needs_parcel_opening:
            require(actor, "parcel.open", action="inward.confirm", target=inward)
        if inward.is_confirmed:
            raise InvalidState(f"{inward} has already been received into stock. It cannot be received twice.")
        if inward.version != expected_version:
            raise StaleVersion(str(inward))
        if not inward.active_lines():
            raise ValidationFailed(["This inward has no lines to receive."])

        now = timezone.now()
        inward.status = Inward.CONFIRMED
        inward.confirmed_by = actor
        inward.confirmed_at = now
        if inward.is_weight_only:
            inward.locked_at = now
            inward.lock_cause = Inward.LOCK_DIRECT_WEIGHT
        inward.version += 1
        inward.save()
        _post_receipt_movements(inward, actor=actor, command="ConfirmInward", retry_key=retry_key)
        audit.record(
            actor=actor,
            action="inward.confirm",
            capability="parcel.open" if inward.needs_parcel_opening else "inward.create",
            target=inward,
            payload={"received": snapshot(inward), "locked": inward.is_locked, "lock_cause": inward.lock_cause},
            retry_key=retry_key,
        )
        return {"inward_id": inward.pk}

    payload = {"inward_id": inward_id, "expected_version": expected_version}
    run_once(command="ConfirmInward", retry_key=retry_key, payload=payload, actor=actor, action=action)
    return Inward.objects.get(pk=inward_id)


def apply_first_lot_lock(inward: Inward, *, actor, retry_key: str) -> None:
    """Lock a tagged-pieces inward because its first lot is being created.

    Not reachable from any screen in this increment. Stage B2's CreateLot
    command must call this inside its own transaction, with the inward row
    already locked by ``select_for_update``, so that a concurrent edit cannot
    slip past the lock (invariant 7).
    """
    if inward.is_locked:
        return
    if not inward.is_confirmed or inward.is_weight_only:
        raise InvalidState("Only a received tagged-pieces inward can be locked by lot creation.")
    inward.locked_at = timezone.now()
    inward.lock_cause = Inward.LOCK_FIRST_LOT
    inward.version += 1
    inward.save(update_fields=["locked_at", "lock_cause", "version"])
    audit.record(
        actor=actor,
        action="inward.lock",
        target=inward,
        payload={"lock_cause": inward.lock_cause},
        retry_key=retry_key,
    )
