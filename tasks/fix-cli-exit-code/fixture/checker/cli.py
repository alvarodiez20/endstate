"""Command line entry point."""

import json
import os


def main(argv, out=print):
    """Check every path in `argv`. Returns a process exit code."""
    for path in argv:
        if not os.path.exists(path):
            out(f"{path}: no such file")
            continue
        with open(path, encoding="utf-8") as handle:
            config = json.load(handle)
        from checker.validate import validate

        problems = validate(config)
        if problems:
            for problem in problems:
                out(f"{path}: {problem}")
        else:
            out(f"{path}: ok")
    return 0
