"""URL slugs."""

import re


def slugify(title):
    """Turn `title` into a lowercase hyphen-separated slug."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
