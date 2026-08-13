`shapes/area.py` dispatches on `shape["kind"]` through a long `if`/`elif`
chain, so every new shape means editing `area()`. Replace it with a registry.

1. Keep `area(shape)` working exactly as it does now, including raising
   `ValueError(f"unknown shape: {kind}")` for an unknown kind.
2. Add `register(kind, function)`, which records a callable taking the shape
   dict and returning its area, so a new shape can be supported **without
   editing `area()`**. Registering a kind that already exists replaces it.
3. Add `registered_kinds()` returning a sorted list of the known kinds.
4. `area()` must contain no `elif` branches when you are done.

Behaviour must not change for the existing shapes. Run
`python -m unittest discover -s tests -t . -q` to check. Do not change
anything under `tests/`.
