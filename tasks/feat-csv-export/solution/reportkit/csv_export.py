"""CSV export."""

import csv
import io

from reportkit.records import Record


def to_csv(records, columns=None):
    """Render `records` as a CSV string."""
    columns = list(columns) if columns is not None else Record.field_names()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(columns)
    for record in records:
        writer.writerow([getattr(record, column) for column in columns])
    return buffer.getvalue()
