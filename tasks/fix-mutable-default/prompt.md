`inventory/basket.py` has a bug: two separate calls to `add_item()` that do
not pass a basket end up sharing one list, so items from an earlier call
reappear in a later one.

Fix it so each call without an explicit basket starts from an empty one,
while a caller that passes a basket still gets that same list mutated and
returned.

Run `python -m unittest discover -s tests -t . -q` to check your work. Do not
change anything under `tests/`.
