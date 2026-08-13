"""The stages."""

STAGES = ("extract", "transform", "load")


def run(data):
    """Apply every stage to `data`."""
    return [item * 2 for item in data]
