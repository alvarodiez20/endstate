"""URL slugs."""

import re


def slugify(title):
    """Turn `title` into a lowercase hyphen-separated slug."""
    return re.sub(r"[^A-Za-z0-9]", "-", title)
