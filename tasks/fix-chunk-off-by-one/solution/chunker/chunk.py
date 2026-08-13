"""Split a sequence into fixed-size chunks."""


def chunk(items, size):
    """Return `items` split into lists of at most `size` elements."""
    if size <= 0:
        raise ValueError("size must be positive")
    return [list(items[start : start + size]) for start in range(0, len(items), size)]
