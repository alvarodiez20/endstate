Add a module `catalogue/summary.py` with a function `describe()` that
returns a single string: every item's name and value, one per line, in
order, formatted exactly as `item-00 = 0`.

You will need to read every module under `catalogue/` to do it. Export
`describe` from `catalogue/__init__.py` as well.

Run `python -m unittest discover -s tests -t . -q` to check your work. Do
not change anything under `tests/`.
