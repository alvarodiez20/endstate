`logkit/access.py` and `logkit/error.py` contain the same line-parsing
algorithm; they differ only in which fields they expect. Factor the shared
algorithm out.

1. Create `logkit/base.py` with `parse_line(line, fields)`, holding the
   algorithm currently duplicated in both modules: split the line on `|`,
   strip each part, return `None` when the number of parts does not match
   the number of fields, and otherwise return a dict zipping `fields` to the
   parts.
2. Rewrite `access.py` and `error.py` so each keeps its `FIELDS` constant and
   its `parse(line)` function, but delegates to `logkit.base.parse_line`.
   The `.split("|")` call must appear once in the package.

Behaviour must not change. Run `python -m unittest discover -s tests -t . -q`
to check. Do not change anything under `tests/`.
