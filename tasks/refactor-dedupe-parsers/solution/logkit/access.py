"""Access log parsing."""

from logkit.base import parse_line

FIELDS = ("timestamp", "method", "path", "status")


def parse(line):
    """Parse one access log line, or return None if it is malformed."""
    return parse_line(line, FIELDS)
