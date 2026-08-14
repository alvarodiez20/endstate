`catalogue/` holds two dozen item modules, each with a `VALUE`. The test
expects `total()` to return the sum of every item's `VALUE`, but
`catalogue/registry.py` is wrong.

Read the item modules, work out the correct sum, and fix `registry.py` so
the test passes. Do not change anything under `tests/`.

Run `python -m unittest discover -s tests -t . -q` to check your work.
