`textkit/slug.py` turns a title into a URL slug. It is meant to produce
lowercase ASCII words joined by single hyphens, with no hyphen at either end.

It currently gets three things wrong: it does not lowercase, it collapses
runs of punctuation into a run of hyphens rather than one, and it leaves a
trailing hyphen when the title ends in punctuation.

Fix `slugify()`. An input with no usable characters must return the empty
string.

Run `python -m unittest discover -s tests -t . -q` to check your work. Do not
change anything under `tests/`.
