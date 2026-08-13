"""Basket operations."""


def add_item(name, quantity=1, basket=None):
    """Add `quantity` of `name` to `basket` and return the basket."""
    if basket is None:
        basket = []
    for _ in range(quantity):
        basket.append(name)
    return basket


def total_items(basket):
    """How many items the basket holds."""
    return len(basket)
