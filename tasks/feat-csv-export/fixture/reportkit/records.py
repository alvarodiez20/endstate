"""The record type."""

from dataclasses import dataclass, fields


@dataclass
class Record:
    """One row of a report."""

    name: str
    region: str
    amount: int

    @classmethod
    def field_names(cls):
        """Field names in declaration order."""
        return [f.name for f in fields(cls)]
