"""Every item's label."""

from catalogue import items


def labels():
    """Each item's LABEL, in declaration order."""
    return [module.LABEL for module in items.ALL]
