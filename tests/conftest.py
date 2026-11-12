import uuid
from decimal import Decimal
from types import SimpleNamespace

import pytest

from demo import fixtures
from inventory import queries
from inventory.models import StockMovement


def key() -> str:
    """A fresh retry key, as a screen would generate for each new form."""
    return uuid.uuid4().hex


def ledger_state() -> dict:
    """Everything that would change if physical stock changed."""
    return {
        "movement_rows": StockMovement.objects.count(),
        "totals": queries.physical_totals(),
        "weight_only": queries.weight_only_balances(),
    }


def weight_only_balance(item) -> Decimal:
    return sum(
        (row["weight"] for row in queries.weight_only_balances() if row["item"] == item.name), Decimal("0")
    )


def _world():
    return SimpleNamespace(m=fixtures.seed_masters(), u=fixtures.seed_access())


@pytest.fixture
def world(db):
    """Synthetic masters and demo users inside a rolled-back test transaction."""
    return _world()


@pytest.fixture
def tworld(transactional_db):
    """Same, but committed, for tests that run real concurrent transactions."""
    return _world()
