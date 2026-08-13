`confkit` reads defaults but ignores everything else. Add layering.

1. Create `confkit/env.py` with `from_env(environ, prefix="APP_")`.
   It turns environment variables into a nested dict: only keys starting
   with `prefix` are considered, the prefix is stripped, the remainder is
   lowercased, and `__` separates nesting levels. So
   `APP_DB__PORT=5432` becomes `{"db": {"port": "5432"}}`.
2. In `confkit/config.py`, add `merge(base, overlay)` returning a new dict
   where `overlay` wins, merging nested dicts recursively rather than
   replacing them wholesale. Neither input may be mutated.
3. Make `load_config(defaults, file_values=None, environ=None, prefix="APP_")`
   apply the layers in order: defaults, then file values, then environment.

Run `python -m unittest discover -s tests -t . -q` to check your work. Do not
change anything under `tests/`.
