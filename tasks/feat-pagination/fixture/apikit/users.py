"""User listing."""

from apikit.store import USERS


def list_users():
    """Every user."""
    return list(USERS)
