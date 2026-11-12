"""Synthetic masters, demo roles and repeatable stock scenarios.

Used by ``manage.py seed_demo`` and by the acceptance tests, so the demo and
the tests exercise the same fixtures (spec: "Preserve these fixtures as the
basis for comparing the owner's build with the consultancy's implementation").

Everything here is synthetic. Role grants and locations are demo configuration,
not agreed production settings (O06, O12). Tolerance values are named demo
settings (O02).
"""

from datetime import date
from decimal import Decimal as D
from types import SimpleNamespace

from accounts.capabilities import CAPABILITIES
from accounts.models import Capability, Role, User
from inventory import services as inventory
from inventory.models import Inward
from inventory.services import InwardInput, InwardLineInput
from masters.models import (
    ChargeDefinition,
    HsnCode,
    Item,
    Karigar,
    Location,
    MakingChargeRule,
    Metal,
    PolicySetting,
    Purity,
    Supplier,
    Unit,
    Variety,
)
from purchasing import services as purchasing
from purchasing.services import InvoiceInput, InvoiceLineInput

DEMO_PASSWORD = "demo-pass-1234"

DEMO_ROLES = {
    "Demo owner (all permissions)": sorted(CAPABILITIES),
    "Demo receiving clerk": ["inward.create", "inward.edit"],
    "Demo parcel verifier": ["inward.create", "inward.edit", "parcel.open"],
    "Demo accounts": ["purchase_invoice.record", "purchase_invoice.match"],
    "Demo viewer": [],
}

DEMO_USERS = {
    "demo_owner": ("Demo", "Owner", "Demo owner (all permissions)"),
    "demo_receiver": ("Demo", "Receiver", "Demo receiving clerk"),
    "demo_verifier": ("Demo", "Verifier", "Demo parcel verifier"),
    "demo_accounts": ("Demo", "Accounts", "Demo accounts"),
    "demo_viewer": ("Demo", "Viewer", "Demo viewer"),
}


def _get(model, defaults=None, **lookup):
    obj, _ = model.objects.get_or_create(defaults=defaults or {}, **lookup)
    return obj


def seed_masters() -> SimpleNamespace:
    m = SimpleNamespace()
    m.g = _get(Unit, code="g", defaults={"name": "Grams", "kind": Unit.WEIGHT, "grams_per_unit": D("1")})
    m.ct = _get(Unit, code="ct", defaults={"name": "Carats", "kind": Unit.WEIGHT, "grams_per_unit": D("0.2")})
    m.nos = _get(Unit, code="Nos", defaults={"name": "Numbers (count)", "kind": Unit.COUNT})

    m.gold = _get(Metal, name="Gold")
    m.silver = _get(Metal, name="Silver")
    m.gold_22k = _get(Purity, name="Gold 22K", defaults={"metal": m.gold, "percentage": D("91.6")})
    m.gold_18k = _get(Purity, name="Gold 18K", defaults={"metal": m.gold, "percentage": D("75")})
    m.silver_925 = _get(Purity, name="Silver 92.5", defaults={"metal": m.silver, "percentage": D("92.5")})

    m.hsn_7113 = _get(
        HsnCode, code="7113", defaults={"description": "Articles of jewellery (demo reference, verify before GST use)"}
    )
    m.hsn_7108 = _get(
        HsnCode, code="7108", defaults={"description": "Gold, unwrought or semi-manufactured (demo reference)"}
    )

    m.chain = _get(Item, name="Chain", defaults={"stock_mode": Item.TAGGABLE, "weight_unit": m.g, "hsn": m.hsn_7113})
    m.ring = _get(Item, name="Ring", defaults={"stock_mode": Item.TAGGABLE, "weight_unit": m.g, "hsn": m.hsn_7113})
    m.bangle = _get(Item, name="Bangle", defaults={"stock_mode": Item.TAGGABLE, "weight_unit": m.g, "hsn": m.hsn_7113})
    m.gold_balls = _get(
        Item, name="Gold Balls", defaults={"stock_mode": Item.WEIGHT_ONLY, "weight_unit": m.g, "hsn": m.hsn_7108}
    )
    m.machine_chain = _get(Variety, item=m.chain, name="Machine Chain")
    m.hollow_chain = _get(Variety, item=m.chain, name="Hollow Chain")
    m.plain_ring = _get(Variety, item=m.ring, name="Plain Ring")

    m.supplier_a = _get(Supplier, name="Synthetic Supplier A", defaults={"notes": "Demo supplier, not a real business."})
    m.supplier_b = _get(Supplier, name="Synthetic Supplier B", defaults={"notes": "Demo supplier, not a real business."})
    m.karigar = _get(Karigar, name="Synthetic Karigar K", defaults={"notes": "Demo karigar, not a real person."})

    m.safe = _get(Location, name="Safe (demo)", defaults={"is_demo": True})
    m.receiving = _get(Location, name="Receiving desk (demo)", defaults={"is_demo": True})
    m.counter = _get(Location, name="Counter 1 (demo)", defaults={"is_demo": True})

    _get(
        MakingChargeRule,
        name="Demo supplier making charge",
        defaults={
            "applies_to": MakingChargeRule.SUPPLIER_PAID,
            "description": "Placeholder name only. Charge units and bases are not decided (O03).",
        },
    )
    _get(
        MakingChargeRule,
        name="Demo customer making charge",
        defaults={
            "applies_to": MakingChargeRule.CUSTOMER_CHARGEABLE,
            "description": "Placeholder name only. Charge units and bases are not decided (O03).",
        },
    )
    _get(ChargeDefinition, name="Demo hallmarking charge", defaults={"description": "Example custom other charge."})

    _get(
        PolicySetting,
        key="demo.lot_weighing_tolerance_mg_per_item",
        defaults={
            "label": "Lot weighing tolerance per item (demo)",
            "value": D("20"),
            "unit": "mg per item",
            "decision_ref": "O02",
            "description": "10 to 20 mg per item is accepted in principle. The exact setting and how it "
            "aggregates are not decided. Not used by any posting yet (lots arrive in stage B2).",
        },
    )
    _get(
        PolicySetting,
        key="demo.box_tolerance_mg",
        defaults={
            "label": "Weight-only box tolerance (demo)",
            "value": D("100"),
            "unit": "mg per box",
            "decision_ref": "O02",
            "description": "100 mg per box was suggested and is tentative. Not used by any posting yet "
            "(box verification arrives in stage B3).",
        },
    )
    return m


def seed_access() -> SimpleNamespace:
    """Create demo roles and one demo user per role."""
    for key, description in CAPABILITIES.items():
        Capability.objects.update_or_create(key=key, defaults={"description": description})
    for name, keys in DEMO_ROLES.items():
        role, created = Role.objects.get_or_create(
            name=name, defaults={"is_demo": True, "description": "Demo configuration, not a production grant."}
        )
        if created:
            role.capabilities.set(Capability.objects.filter(key__in=keys))
    users = SimpleNamespace()
    for username, (first, last, role_name) in DEMO_USERS.items():
        user, created = User.objects.get_or_create(
            username=username, defaults={"first_name": first, "last_name": last}
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.save()
            user.roles.set([Role.objects.get(name=role_name)])
        setattr(users, username.removeprefix("demo_"), user)
    return users


# --------------------------------------------------------------------------
# Scenarios. Each uses fixed retry keys, so running it again changes nothing.
# --------------------------------------------------------------------------

def _receive(u, key: str, data: InwardInput, *, confirm: bool = True) -> Inward:
    inward = inventory.create_inward(actor=u.receiver, data=data, retry_key=f"{key}-create")
    if confirm and not inward.is_confirmed:
        inward = inventory.confirm_inward(
            actor=u.verifier, inward_id=inward.pk, expected_version=inward.version, retry_key=f"{key}-confirm"
        )
    return inward


def t01_receipt_then_invoice(m, u, prefix: str = "demo-t01"):
    """T01: receive 10 chains (100 g), then enter and match the supplier invoice."""
    inward = _receive(
        u,
        prefix,
        InwardInput(
            source_type=Inward.SUPPLIER_PURCHASE,
            stock_mode=Item.TAGGABLE,
            supplier_id=m.supplier_a.pk,
            source_reference="SA/DC/1001",
            source_date=date(2026, 11, 10),
            location_id=m.receiving.pk,
            notes="Synthetic T01 fixture.",
            lines=(
                InwardLineInput(
                    item_id=m.chain.pk,
                    purity_id=m.gold_22k.pk,
                    declared_pieces=10,
                    declared_gross_weight=D("100.000"),
                    declared_net_weight=D("100.000"),
                    actual_pieces=10,
                    actual_gross_weight=D("100.000"),
                    actual_net_weight=D("100.000"),
                ),
            ),
        ),
    )
    invoice = purchasing.record_supplier_invoice(
        actor=u.accounts,
        data=InvoiceInput(
            supplier_id=m.supplier_a.pk,
            invoice_number=f"SA/INV/{prefix}",
            invoice_date=date(2026, 11, 11),
            stated_total_value=D("700000.00"),
            notes="Synthetic T01 fixture. Stated values are document values only.",
            lines=(
                InvoiceLineInput(
                    description="22K gold chains",
                    item_id=m.chain.pk,
                    purity_id=m.gold_22k.pk,
                    hsn_code="7113",
                    stated_pieces=10,
                    stated_gross_weight=D("100.000"),
                    stated_net_weight=D("100.000"),
                    stated_value=D("700000.00"),
                ),
            ),
        ),
        retry_key=f"{prefix}-invoice",
    )
    match = purchasing.match_invoice_line(
        actor=u.accounts,
        invoice_line_id=invoice.lines.get().pk,
        inward_line_id=inward.lines.get().pk,
        retry_key=f"{prefix}-match",
    )
    return SimpleNamespace(inward=inward, invoice=invoice, match=match)


def t08_gold_balls_on_approval(m, u, prefix: str = "demo-t08") -> Inward:
    """T08 (receipt part): 100 g of weight-only gold balls on a supplier approval memo."""
    return _receive(
        u,
        prefix,
        InwardInput(
            source_type=Inward.SUPPLIER_APPROVAL,
            stock_mode=Item.WEIGHT_ONLY,
            supplier_id=m.supplier_b.pk,
            source_reference="SB/APP/2001",
            source_date=date(2026, 11, 10),
            location_id=m.safe.pk,
            notes="Synthetic T08 fixture.",
            lines=(
                InwardLineInput(
                    item_id=m.gold_balls.pk,
                    purity_id=m.gold_22k.pk,
                    declared_gross_weight=D("100.000"),
                    actual_gross_weight=D("100.000"),
                ),
            ),
        ),
    )


def t02_chain_receipt(m, u, prefix: str = "demo-t02") -> Inward:
    """T02 (receipt part): 200 g of chains including one damaged 15 g hollow chain.

    The full quantity is received. Lots by variety arrive in stage B2.
    """
    return _receive(
        u,
        prefix,
        InwardInput(
            source_type=Inward.SUPPLIER_PURCHASE,
            stock_mode=Item.TAGGABLE,
            supplier_id=m.supplier_a.pk,
            source_reference="SA/DC/1002",
            source_date=date(2026, 11, 11),
            location_id=m.receiving.pk,
            notes="Synthetic T02 fixture.",
            lines=(
                InwardLineInput(
                    item_id=m.chain.pk,
                    purity_id=m.gold_22k.pk,
                    declared_pieces=20,
                    declared_gross_weight=D("200.000"),
                    declared_net_weight=D("200.000"),
                    actual_pieces=20,
                    actual_gross_weight=D("200.000"),
                    actual_net_weight=D("200.000"),
                    condition_notes="100 g machine chains and 100 g hollow chains. "
                    "One hollow chain of 15 g is damaged and is received with the rest.",
                ),
            ),
        ),
    )


def t07_approval_pieces(m, u, prefix: str = "demo-t07") -> Inward:
    """T07 (receipt part): approval inward of 10 pieces, 100 g."""
    return _receive(
        u,
        prefix,
        InwardInput(
            source_type=Inward.SUPPLIER_APPROVAL,
            stock_mode=Item.TAGGABLE,
            supplier_id=m.supplier_b.pk,
            source_reference="SB/APP/2002",
            source_date=date(2026, 11, 11),
            location_id=m.receiving.pk,
            notes="Synthetic T07 fixture.",
            lines=(
                InwardLineInput(
                    item_id=m.ring.pk,
                    purity_id=m.gold_22k.pk,
                    declared_pieces=10,
                    declared_gross_weight=D("100.000"),
                    declared_net_weight=D("100.000"),
                    actual_pieces=10,
                    actual_gross_weight=D("100.000"),
                    actual_net_weight=D("100.000"),
                ),
            ),
        ),
    )


def draft_karigar_inward(m, u, prefix: str = "demo-karigar") -> Inward:
    """A draft with a declared-versus-actual difference, left open for the edit demo."""
    return _receive(
        u,
        prefix,
        InwardInput(
            source_type=Inward.KARIGAR_INWARD,
            stock_mode=Item.TAGGABLE,
            karigar_id=m.karigar.pk,
            source_reference="KK/SLIP/31",
            source_date=date(2026, 11, 12),
            location_id=m.receiving.pk,
            notes="Synthetic draft. Not yet received into stock.",
            lines=(
                InwardLineInput(
                    item_id=m.bangle.pk,
                    purity_id=m.gold_22k.pk,
                    declared_pieces=4,
                    declared_gross_weight=D("50.000"),
                    declared_net_weight=D("50.000"),
                    actual_pieces=4,
                    actual_gross_weight=D("49.950"),
                    actual_net_weight=D("49.950"),
                    condition_notes="Weighed 50 mg under the karigar's slip.",
                ),
            ),
        ),
        confirm=False,
    )


def seed_all() -> SimpleNamespace:
    m = seed_masters()
    u = seed_access()
    return SimpleNamespace(
        masters=m,
        users=u,
        t01=t01_receipt_then_invoice(m, u),
        t08=t08_gold_balls_on_approval(m, u),
        t02=t02_chain_receipt(m, u),
        t07=t07_approval_pieces(m, u),
        draft=draft_karigar_inward(m, u),
    )
