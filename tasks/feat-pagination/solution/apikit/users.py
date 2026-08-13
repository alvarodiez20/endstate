"""User listing."""

from apikit.pagination import paginate
from apikit.store import USERS


def list_users(page=1, per_page=20):
    """One page of users."""
    return paginate(USERS, page=page, per_page=per_page)
