"""Error log parsing."""

FIELDS = ("timestamp", "level", "message")


def parse(line):
    """Parse one error log line, or return None if it is malformed."""
    parts = [part.strip() for part in line.split("|")]
    if len(parts) != len(FIELDS):
        return None
    return dict(zip(FIELDS, parts))
