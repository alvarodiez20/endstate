"""Area calculation."""

import math


def area(shape):
    """The area of `shape`, a dict with a "kind" key."""
    kind = shape["kind"]
    if kind == "square":
        return shape["side"] ** 2
    elif kind == "rectangle":
        return shape["width"] * shape["height"]
    elif kind == "circle":
        return math.pi * shape["radius"] ** 2
    elif kind == "triangle":
        return 0.5 * shape["base"] * shape["height"]
    elif kind == "trapezoid":
        return 0.5 * (shape["a"] + shape["b"]) * shape["height"]
    else:
        raise ValueError(f"unknown shape: {kind}")
