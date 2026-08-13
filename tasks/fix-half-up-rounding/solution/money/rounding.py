"""Round monetary amounts to cents."""

from decimal import ROUND_HALF_UP, Decimal


def round_cents(value):
    """Round `value` to two decimal places, half away from zero."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_cents(value):
    """Render `value` as a two-decimal string."""
    return f"{round_cents(value):.2f}"
