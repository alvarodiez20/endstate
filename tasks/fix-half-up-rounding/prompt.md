`money/rounding.py` must round monetary amounts to two decimal places using
**half-up** rounding: a value exactly halfway between two cents always goes
to the larger magnitude, so 0.125 becomes 0.13 and -0.125 becomes -0.13.

The current implementation uses the builtin `round()`, which does
banker's rounding on binary floats, so 0.125 becomes 0.12 and 2.675 becomes
2.67.

Fix `round_cents()` so it follows the spec. It takes a float or a string and
returns a `decimal.Decimal` with exactly two places. `format_cents()` must
keep working unchanged.

Run `python -m unittest discover -s tests -t . -q` to check your work. Do not
change anything under `tests/`.
