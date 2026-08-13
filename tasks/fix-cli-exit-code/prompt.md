`checker/cli.py` validates config files. When a file is invalid it prints the
problems, and then returns 0 anyway — so a CI job calling it never fails.

Fix `main()` so it returns 0 only when every file checked is valid, and 1
when any file is invalid or missing. Keep the printed output exactly as it
is; only the return value is wrong.

Run `python -m unittest discover -s tests -t . -q` to check your work. Do not
change anything under `tests/`.
