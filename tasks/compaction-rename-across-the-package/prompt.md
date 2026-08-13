Every module in `catalogue/` exposes a constant called `NAME`. It has to be
called `LABEL` instead, everywhere, with the same values.

`catalogue/naming.py` collects them and is already written against `LABEL`,
so the test will pass once every item module is renamed. Do not change
anything under `tests/` or `catalogue/naming.py`.

Run `python -m unittest discover -s tests -t . -q` to check your work.
