"""Validate a config mapping."""

REQUIRED = ("name", "version")


def validate(config):
    """Return a list of problems; empty means valid."""
    problems = []
    for key in REQUIRED:
        if key not in config:
            problems.append(f"missing key: {key}")
    if "version" in config and not str(config["version"]).strip():
        problems.append("version is empty")
    return problems
