"""Round monetary amounts to cents."""

from decimal import Decimal


def round_cents(value):
    """Round `value` to two decimal places, half away from zero."""
    return Decimal(str(round(float(value), 2)))


def format_cents(value):
    """Render `value` as a two-decimal string."""
    return f"{round_cents(value):.2f}"
