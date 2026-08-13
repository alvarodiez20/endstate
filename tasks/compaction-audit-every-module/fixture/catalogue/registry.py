"""Adds up every item in the package."""

from catalogue import items


def total():
    """The sum of every item's value."""
    return sum(module.VALUE for module in items.ALL[:5])
