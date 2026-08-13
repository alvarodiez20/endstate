`apikit` returns every row from both of its listing functions. Add
pagination and use it in both places.

1. Create `apikit/pagination.py` with a `Page` dataclass carrying
   `items`, `page`, `per_page`, `total` and a `pages` property (the total
   number of pages, at least 1 even when there are no items), plus a
   function `paginate(items, page=1, per_page=20)` returning a `Page`.
   - Pages are one-based. `page` below 1 or `per_page` below 1 raises
     `ValueError`.
   - A page past the end has empty `items` but still reports the real
     `total`.
2. Change `list_users()` in `apikit/users.py` and `list_orders()` in
   `apikit/orders.py` to accept `page=1, per_page=20` and return a `Page`.

Run `python -m unittest discover -s tests -t . -q` to check your work. Do not
change anything under `tests/`.
