"""The client."""

import time

from netkit.retry import retry


class TransportError(Exception):
    """The transport failed in a way that may be transient."""


def fetch(transport, url, sleep=time.sleep):
    """Fetch `url` through `transport`, retrying transient failures."""

    @retry(attempts=3, exceptions=(TransportError,), sleep=sleep)
    def attempt():
        return transport(url)

    return attempt()
