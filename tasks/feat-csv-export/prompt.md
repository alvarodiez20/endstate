`reportkit` can build records but cannot export them. Add CSV export.

1. Create `reportkit/csv_export.py` with a function
   `to_csv(records, columns=None)` that returns a CSV string.
   - The header row is the column names.
   - `columns` defaults to the fields of `Record`, in declaration order.
   - Rows come out in the order they were passed.
   - Use the standard library `csv` module and `\r\n` line endings (the
     `csv` module's default).
   - An empty record list still produces the header row.
2. Export `to_csv` from `reportkit/__init__.py` so `from reportkit import
   to_csv` works, and add it to `__all__`.

Run `python -m unittest discover -s tests -t . -q` to check your work. Do not
change anything under `tests/`.
