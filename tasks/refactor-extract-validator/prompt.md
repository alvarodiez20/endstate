`formkit` has the same email and password validation copy-pasted into
`signup.py`, `login.py` and `reset.py`. Extract it, without changing what
any of the three functions do.

1. Create `formkit/validation.py` with `validate_email(email)` and
   `validate_password(password)`. Each returns a list of problem strings —
   empty means valid — using exactly the messages the current code produces.
2. Rewrite `signup.py`, `login.py` and `reset.py` to call those two
   functions. The `EMAIL_PATTERN` regex must appear in one place only, and
   the three modules must keep their current public functions and their
   current return values.

Behaviour must not change. Run `python -m unittest discover -s tests -t . -q`
to check. Do not change anything under `tests/`.
