"""Exact numeric handling for weights, carats, percentages and money.

Everything here uses decimal.Decimal. Binary floats are rejected at the
boundary so that 10 mg steps and the 1 ct = 0.200 g conversion never drift.
Rounding rules are open (O02, O03); nothing in this module rounds silently:
a value with more precision than can be stored is refused, not trimmed.
"""

from decimal import Decimal, InvalidOperation

# Stored precision. 0.0001 g represents 10 mg and 0.001 ct (0.0002 g) exactly.
WEIGHT_MAX_DIGITS = 14
WEIGHT_DECIMAL_PLACES = 4
MONEY_MAX_DIGITS = 14
MONEY_DECIMAL_PLACES = 2
PERCENT_MAX_DIGITS = 7
PERCENT_DECIMAL_PLACES = 4

GRAMS_PER_CARAT = Decimal("0.2")


def to_decimal(value, *, places: int, what: str) -> Decimal:
    """Convert operator or API input to an exact Decimal.

    Raises ValueError for floats, non-numbers and values that would need
    rounding to fit the stored precision.
    """
    if isinstance(value, float):
        raise ValueError(f"{what}: binary floating-point values are not accepted; send a decimal string")
    if isinstance(value, bool):
        raise ValueError(f"{what}: not a number")
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        raise ValueError(f"{what}: '{value}' is not a number") from None
    if not number.is_finite():
        raise ValueError(f"{what}: '{value}' is not a number")
    quantum = Decimal(1).scaleb(-places)
    if number != number.quantize(quantum):
        raise ValueError(f"{what}: {number} has more than {places} decimal places")
    return number.quantize(quantum)


def carats_to_grams(carats: Decimal) -> Decimal:
    """Explicit unit conversion: 1 ct = 0.200 g. Exact for any stored carat value."""
    if not isinstance(carats, Decimal):
        raise TypeError("carats must be a Decimal")
    return carats * GRAMS_PER_CARAT


def canonical(value: Decimal | None, places: int = WEIGHT_DECIMAL_PLACES) -> str | None:
    """Stable text form used in audit payloads and retry-key payload hashes."""
    if value is None:
        return None
    return str(value.quantize(Decimal(1).scaleb(-places)))


def show(value: Decimal) -> str:
    """Weight as staff read it: 3 decimals, or 4 when the fourth is not zero."""
    thousandths = value.quantize(Decimal("0.001"))
    return f"{thousandths:.3f}" if thousandths == value else f"{value:.4f}"
