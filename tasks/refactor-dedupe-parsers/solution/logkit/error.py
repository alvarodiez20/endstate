"""Error log parsing."""

from logkit.base import parse_line

FIELDS = ("timestamp", "level", "message")


def parse(line):
    """Parse one error log line, or return None if it is malformed."""
    return parse_line(line, FIELDS)
