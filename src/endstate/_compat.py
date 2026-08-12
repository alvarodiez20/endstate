"""Shims for the Python versions this package supports.

Kept deliberately small. Anything here is a cost of the support window, so it
should shrink as versions age out rather than grow.
"""

import sys
from enum import Enum

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:  # pragma: no cover - exercised on 3.10 in CI, not on the version that measures coverage

    class StrEnum(str, Enum):
        """`enum.StrEnum`, which landed in 3.11.

        Subclassing `str` alone is not enough: on 3.11+ a plain `str, Enum` mixin
        renders as `Decision.ALLOW` rather than `allow`. Taking `str.__str__` is
        what makes the two behave identically in f-strings, logs and payloads.
        """

        __str__ = str.__str__


__all__ = ["StrEnum"]
