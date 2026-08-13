`netkit` calls a flaky transport with no retries. Add them.

1. Create `netkit/retry.py` with a decorator factory
   `retry(attempts=3, delay=0.1, backoff=2.0, exceptions=(Exception,), sleep=time.sleep)`.
   - It calls the wrapped function up to `attempts` times.
   - It only retries the exception types in `exceptions`; anything else
     propagates immediately.
   - Between attempts it calls `sleep(d)` where `d` starts at `delay` and is
     multiplied by `backoff` after each failed attempt.
   - If every attempt fails, the last exception propagates.
   - Use `functools.wraps` so the wrapped function keeps its `__name__`.
2. In `netkit/client.py`, make `fetch()` retry `TransportError` three times.
   `fetch` must accept a `sleep` argument, defaulting to `time.sleep`, and
   pass it through, so tests do not have to wait.

Run `python -m unittest discover -s tests -t . -q` to check your work. Do not
change anything under `tests/`.
