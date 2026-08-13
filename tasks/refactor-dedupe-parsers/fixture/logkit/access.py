"""Access log parsing."""

FIELDS = ("timestamp", "method", "path", "status")


def parse(line):
    """Parse one access log line, or return None if it is malformed."""
    parts = [part.strip() for part in line.split("|")]
    if len(parts) != len(FIELDS):
        return None
    return dict(zip(FIELDS, parts))
