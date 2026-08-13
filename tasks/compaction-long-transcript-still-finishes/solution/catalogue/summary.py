"""A one-line-per-item summary."""

from catalogue import items


def describe():
    """Every item's name and value, one per line."""
    return "\n".join(f"{module.NAME} = {module.VALUE}" for module in items.ALL)
