`pipeline/stages.py` has a `run()` that raises instead of doing anything. Make
it return each item of `data` doubled, so the tests pass.

Run `python -m unittest discover -s tests -t . -q` to check your work. Do not
change anything under `tests/`.
