"""Area calculation."""

import math

_AREAS = {}


def register(kind, function):
    """Record how to compute the area of `kind`."""
    _AREAS[kind] = function


def registered_kinds():
    """Every known shape kind, sorted."""
    return sorted(_AREAS)


def area(shape):
    """The area of `shape`, a dict with a "kind" key."""
    kind = shape["kind"]
    try:
        calculate = _AREAS[kind]
    except KeyError:
        raise ValueError(f"unknown shape: {kind}") from None
    return calculate(shape)


register("square", lambda s: s["side"] ** 2)
register("rectangle", lambda s: s["width"] * s["height"])
register("circle", lambda s: math.pi * s["radius"] ** 2)
register("triangle", lambda s: 0.5 * s["base"] * s["height"])
register("trapezoid", lambda s: 0.5 * (s["a"] + s["b"]) * s["height"])
