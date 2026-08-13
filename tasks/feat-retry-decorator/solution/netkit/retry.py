"""Retry with backoff."""

import functools
import time


def retry(attempts=3, delay=0.1, backoff=2.0, exceptions=(Exception,), sleep=time.sleep):
    """Retry the wrapped callable up to `attempts` times."""

    def decorate(function):
        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            wait = delay
            for attempt in range(1, attempts + 1):
                try:
                    return function(*args, **kwargs)
                except exceptions:
                    if attempt == attempts:
                        raise
                    sleep(wait)
                    wait *= backoff
            raise AssertionError("unreachable")

        return wrapper

    return decorate
