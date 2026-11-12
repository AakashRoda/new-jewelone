"""The operator screens, driven through HTTP the way a browser would."""

from decimal import Decimal as D

import pytest
from django.urls import reverse

from audit.models import AuditEvent
from demo import fixtures
from inventory.models import Inward, StockMovement
from masters.models import Metal
from purchasing.models import InvoiceMatch, SupplierInvoice
from tests.conftest import key, ledger_state


@pytest.fixture
def seeded(db):
    return fixtures.seed_all()


def login(client, user):
    client.force_login(user)
    return client


def line_post(index=0, prefix="lines", **fields):
    return {f"{prefix}-{index}-{name}": value for name, value in fields.items()}


def formset_post(total, initial=0, prefix="lines"):
    return {
        f"{prefix}-TOTAL_FORMS": str(total),
        f"{prefix}-INITIAL_FORMS": str(initial),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }


def test_smoke_health_check_needs_no_login(client, db):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "pending_migrations": 0}


def test_everything_else_needs_a_login(client, db):
    response = client.get(reverse("stock-overview"))
    assert response.status_code == 302 and response.url.startswith("/login/")


def test_every_screen_renders_for_the_demo_owner(client, seeded):
    login(client, seeded.users.owner)
    invoice = seeded.t01.invoice
    urls = [
        reverse("stock-overview"),
        reverse("inward-list"),
        reverse("inward-list") + "?status=draft",
        reverse("inward-new", args=["taggable"]),
        reverse("inward-new", args=["weight_only"]),
        reverse("inward-detail", args=[seeded.t01.inward.pk]),
        reverse("inward-detail", args=[seeded.t08.pk]),
        reverse("inward-detail", args=[seeded.draft.pk]),
        reverse("inward-edit", args=[seeded.draft.pk]),
        reverse("inward-edit", args=[seeded.t02.pk]),
        reverse("inward-confirm", args=[seeded.draft.pk]),
        reverse("invoice-list"),
        reverse("invoice-new"),
        reverse("invoice-detail", args=[invoice.pk]),
        reverse("invoice-match", args=[invoice.lines.get().pk]),
        reverse("invoice-match-remove", args=[seeded.t01.match.pk]),
        reverse("masters-index"),
        reverse("audit-list"),
        reverse("audit-list") + "?outcome=denied",
        reverse("access-index"),
        reverse("role-new"),
        reverse("user-new"),
        reverse("user-edit", args=[seeded.users.viewer.pk]),
    ]
    from masters.views import MASTERS

    for slug, (model, *_rest) in MASTERS.items():
        urls += [reverse("master-list", args=[slug]), reverse("master-new", args=[slug])]
        first = model.objects.first()
        if first:
            urls.append(reverse("master-edit", args=[slug, first.pk]))
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200, f"{url} gave {response.status_code}"


def test_stock_overview_separates_untagged_and_weight_only_stock(client, seeded):
    login(client, seeded.users.viewer)
    html = client.get(reverse("stock-overview")).content.decode()
    assert "Untagged pieces, received and waiting for lots" in html
    assert "100.000 g" in html and "Gold Balls" in html
    assert "INW-" in html
    assert "draft inward" in html


def test_receiving_weight_only_stock_through_the_screens(client, seeded):
    m, u = seeded.masters, seeded.users
    login(client, u.owner)
    retry_key = key()
    post = {
        "retry_key": retry_key,
        "source_type": "supplier_approval",
        "supplier": m.supplier_b.pk,
        "source_reference": "SB/APP/9",
        "location": m.safe.pk,
        **formset_post(1),
        **line_post(item=m.gold_balls.pk, purity=m.gold_22k.pk, declared_gross_weight="25.000", actual_gross_weight="24.990"),
    }
    url = reverse("inward-new", args=["weight_only"])
    response = client.post(url, post)
    assert response.status_code == 302
    inward = Inward.objects.latest("id")
    assert inward.status == Inward.DRAFT and StockMovement.objects.filter(inward_line__inward=inward).count() == 0

    # A double-submitted form (same retry key) does not create a second inward.
    count = Inward.objects.count()
    assert client.post(url, post).status_code == 302
    assert Inward.objects.count() == count

    detail = client.get(reverse("inward-detail", args=[inward.pk])).content.decode()
    assert "not in stock" in detail and "−0.010" in detail

    confirm_url = reverse("inward-confirm", args=[inward.pk])
    assert "locks immediately" in client.get(confirm_url).content.decode()
    confirm_post = {"retry_key": key(), "expected_version": inward.version}
    assert client.post(confirm_url, confirm_post).status_code == 302
    assert client.post(confirm_url, confirm_post).status_code == 302  # double-click, same key
    inward.refresh_from_db()
    assert inward.is_locked
    assert StockMovement.objects.filter(inward_line__inward=inward).count() == 1

    # The locked inward explains why it cannot be edited, and the edit screen refuses.
    detail = client.get(reverse("inward-detail", args=[inward.pk])).content.decode()
    assert "Locked." in detail and "O01" in detail and "Edit (a reason is required)" not in detail
    state = ledger_state()
    response = client.post(
        reverse("inward-edit", args=[inward.pk]),
        {**post, "reason": "Trying to change a locked receipt", "expected_version": inward.version, "retry_key": key()},
    )
    assert response.status_code == 302
    assert ledger_state() == state
    assert inward.lines.get().actual_gross_weight == D("24.9900")


def test_editing_a_draft_needs_a_reason_and_keeps_what_was_typed(client, seeded):
    m, u = seeded.masters, seeded.users
    login(client, u.receiver)
    draft = seeded.draft
    line = draft.lines.get()
    post = {
        "retry_key": key(),
        "expected_version": draft.version,
        "source_type": "karigar_inward",
        "karigar": m.karigar.pk,
        "source_reference": "KK/SLIP/31",
        "location": m.receiving.pk,
        **formset_post(1, initial=1),
        **line_post(
            id=line.pk, item=m.bangle.pk, purity=m.gold_22k.pk, declared_pieces="4",
            declared_gross_weight="50.000", declared_net_weight="50.000",
            actual_pieces="4", actual_gross_weight="49.975", actual_net_weight="49.975",
        ),
    }
    url = reverse("inward-edit", args=[draft.pk])

    response = client.post(url, {**post, "reason": ""})
    assert response.status_code == 422
    html = response.content.decode()
    assert 'value="49.975"' in html, "typed values are kept after an error"
    line.refresh_from_db()
    assert line.actual_gross_weight == D("49.9500")

    # Net above gross: the message names the line and both quantities.
    bad = {**post, "reason": "Re-weighed", "lines-0-actual_net_weight": "60.000"}
    response = client.post(url, bad)
    assert response.status_code == 422
    assert "Line 1: net weight 60.000 g cannot be more than gross weight 49.975 g" in response.content.decode()

    assert client.post(url, {**post, "reason": "Re-weighed on the second scale"}).status_code == 302
    line.refresh_from_db()
    assert line.actual_gross_weight == D("49.9750")
    history = client.get(reverse("inward-detail", args=[draft.pk])).content.decode()
    assert "Re-weighed on the second scale" in history and "49.9500 → " in history


def test_viewer_cannot_enter_edit_or_receive(client, seeded):
    u = seeded.users
    login(client, u.viewer)
    state = ledger_state()
    assert client.get(reverse("inward-new", args=["taggable"])).status_code == 403
    assert client.get(reverse("inward-edit", args=[seeded.draft.pk])).status_code == 403
    assert client.get(reverse("invoice-new")).status_code == 403
    assert client.get(reverse("audit-list")).status_code == 403
    assert client.get(reverse("role-new")).status_code == 403
    assert client.get(reverse("master-new", args=["metals"])).status_code == 403
    assert client.post(reverse("master-new", args=["metals"]), {"name": "Platinum", "is_active": "on"}).status_code == 403
    response = client.post(
        reverse("inward-confirm", args=[seeded.draft.pk]), {"retry_key": key(), "expected_version": seeded.draft.version}
    )
    assert response.status_code == 422 and "do not have the permission" in response.content.decode()
    assert ledger_state() == state
    assert not Metal.objects.filter(name="Platinum").exists()
    detail = client.get(reverse("inward-detail", args=[seeded.draft.pk])).content.decode()
    assert "Check and receive into stock" not in detail


def test_receiving_clerk_is_told_why_a_supplier_parcel_cannot_be_confirmed(client, seeded):
    m, u = seeded.masters, seeded.users
    draft = fixtures._receive(
        u, "screen-parcel", fixtures.inventory.InwardInput(
            source_type=Inward.SUPPLIER_PURCHASE, stock_mode="taggable", supplier_id=m.supplier_a.pk,
            location_id=m.receiving.pk,
            lines=(fixtures.InwardLineInput(item_id=m.chain.pk, purity_id=m.gold_22k.pk, actual_pieces=1,
                                            actual_gross_weight=D("10"), actual_net_weight=D("10")),),
        ), confirm=False,
    )
    login(client, u.receiver)
    html = client.get(reverse("inward-detail", args=[draft.pk])).content.decode()
    assert "parcel.open" in html and "Check and receive into stock" not in html


def test_entering_and_linking_an_invoice_through_the_screens(client, seeded):
    m, u = seeded.masters, seeded.users
    login(client, u.accounts)
    state = ledger_state()
    post = {
        "retry_key": key(),
        "supplier": m.supplier_b.pk,
        "invoice_number": "SB/INV/77",
        "invoice_date": "2026-11-20",
        "stated_total_value": "350000.00",
        **formset_post(1),
        **line_post(description="22K gold balls retained", item=m.gold_balls.pk, purity=m.gold_22k.pk, stated_gross_weight="50.000"),
    }
    assert client.post(reverse("invoice-new"), post).status_code == 302
    invoice = SupplierInvoice.objects.get(invoice_number="SB/INV/77")
    assert ledger_state() == state

    # Entering the same invoice again with a fresh form is refused with a clear message.
    response = client.post(reverse("invoice-new"), {**post, "retry_key": key()})
    assert response.status_code == 422 and "already been entered" in response.content.decode()

    pick_url = reverse("invoice-match", args=[invoice.lines.get().pk])
    html = client.get(pick_url).content.decode()
    assert seeded.t08.number in html and seeded.t01.inward.number not in html, "only this supplier's receipts are offered"
    inward_line = seeded.t08.lines.get()
    assert client.post(pick_url, {"retry_key": key(), "inward_line": inward_line.pk}).status_code == 302
    assert client.post(pick_url, {"retry_key": key(), "inward_line": inward_line.pk}).status_code == 302
    assert InvoiceMatch.objects.filter(invoice_line__invoice=invoice, removed_at__isnull=True).count() == 1
    assert ledger_state() == state
    detail = client.get(reverse("invoice-detail", args=[invoice.pk])).content.decode()
    assert seeded.t08.number in detail and "₹3,50,000.00" in detail

    match = InvoiceMatch.objects.get(invoice_line__invoice=invoice)
    remove_url = reverse("invoice-match-remove", args=[match.pk])
    assert client.post(remove_url, {"retry_key": key(), "reason": ""}).status_code == 422
    assert client.post(remove_url, {"retry_key": key(), "reason": "Linked to the wrong memo"}).status_code == 302
    assert ledger_state() == state


def test_master_and_role_changes_are_recorded(client, seeded):
    u = seeded.users
    login(client, u.owner)
    assert client.post(reverse("master-new", args=["metals"]), {"name": "Platinum", "is_active": "on"}).status_code == 302
    metal = Metal.objects.get(name="Platinum")
    assert client.post(reverse("master-edit", args=["metals", metal.pk]), {"name": "Platinum 950", "is_active": "on"}).status_code == 302
    event = AuditEvent.objects.filter(action="master.update").latest("id")
    assert event.payload["before"]["name"] == "Platinum" and event.payload["after"]["name"] == "Platinum 950"
    assert event.actor == u.owner

    role = u.viewer.roles.get()
    from accounts.models import Capability

    cap = Capability.objects.get(key="audit.view")
    response = client.post(
        reverse("role-edit", args=[role.pk]),
        {"name": role.name, "description": role.description, "is_demo": "on", "capabilities": [cap.pk]},
    )
    assert response.status_code == 302
    assert u.viewer.has_capability("audit.view")
    event = AuditEvent.objects.filter(action="role.update").latest("id")
    assert event.payload["before"]["capabilities"] == [] and event.payload["after"]["capabilities"] == ["audit.view"]
