"""Order listing."""

from apikit.store import ORDERS


def list_orders():
    """Every order."""
    return list(ORDERS)
