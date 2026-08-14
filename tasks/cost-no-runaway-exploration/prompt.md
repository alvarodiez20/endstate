One function in this repository is wrong: `catalogue/registry.py` sums only
the first five items instead of all of them. Fix it.

The rest of the package is fine and does not need reading in full. Run
`python -m unittest discover -s tests -t . -q` to check your work. Do not
change anything under `tests/`.
