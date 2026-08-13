"""The client."""

import time


class TransportError(Exception):
    """The transport failed in a way that may be transient."""


def fetch(transport, url, sleep=time.sleep):
    """Fetch `url` through `transport`."""
    return transport(url)
