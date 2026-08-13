"""Order listing."""

from apikit.pagination import paginate
from apikit.store import ORDERS


def list_orders(page=1, per_page=20):
    """One page of orders."""
    return paginate(ORDERS, page=page, per_page=per_page)
