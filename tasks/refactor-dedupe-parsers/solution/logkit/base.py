"""The shared parsing algorithm."""


def parse_line(line, fields):
    """Parse one pipe-separated line, or return None if it is malformed."""
    parts = [part.strip() for part in line.split("|")]
    if len(parts) != len(fields):
        return None
    return dict(zip(fields, parts))
