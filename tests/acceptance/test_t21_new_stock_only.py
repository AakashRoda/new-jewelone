"""T21 (C01), the parts that belong to stage B1.

Add new taggable and untaggable stock. Expected: untaggable stock enters by
weight; taggable stock is received through this software and waits for this
application's own tagging workflow (stage B2). No old-tag import exists.
"""

from decimal import Decimal as D

from django.core.management import get_commands
from django.urls import get_resolver

from demo import fixtures
from inventory import queries
from inventory.models import InwardLine
from tests.conftest import weight_only_balance


def test_t21_new_stock_enters_only_through_inwards(world):
    m, u = world.m, world.u
    taggable = fixtures.t07_approval_pieces(m, u, prefix="t21-tag")
    fixtures.t08_gold_balls_on_approval(m, u, prefix="t21-weight")

    # Untaggable stock: by weight, straight into the item's balance.
    assert weight_only_balance(m.gold_balls) == D("100.0000")

    # Taggable stock: received in full and waiting for lots and new tags.
    waiting = list(queries.received_awaiting_lots())
    assert [line.inward_id for line in waiting] == [taggable.pk]
    assert (waiting[0].actual_pieces, waiting[0].actual_gross_weight) == (10, D("100.0000"))

    # A receipt line has nowhere to carry a tag number from another system.
    field_names = {field.name for field in InwardLine._meta.get_fields()}
    assert not {name for name in field_names if "tag" in name or "rfid" in name or "legacy" in name}


def test_t21_no_old_tag_import_workflow_exists():
    commands = set(get_commands())
    assert not {name for name in commands if "import" in name}

    def names(patterns):
        for pattern in patterns:
            if hasattr(pattern, "url_patterns"):
                yield from names(pattern.url_patterns)
            elif pattern.name:
                yield pattern.name

    assert not {name for name in names(get_resolver().url_patterns) if "import" in name}
