"""Deterministic hashing of a directory tree.

The project's whole claim is that an agent is judged by what it left behind, so
the harness needs a way to say "this sandbox is byte-for-byte what it was" and
"these two runs finished in the same place". That sentence is this module.

Two properties matter and both are deliberate:

*Deterministic.* Entries are collected and sorted before anything is hashed, so
the digest never depends on filesystem iteration order.

*Content, not metadata.* Modification times, inode numbers and ownership are
ignored — two runs that produce identical files an hour apart must agree. The
executable bit is the one piece of metadata included, because `chmod +x` is a
real change an agent can make.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

DEFAULT_EXCLUDES = frozenset(
    {
        ".git",  # commit objects embed timestamps; the working tree is what matters
        ".endstate",  # the harness's own session database
        "__pycache__",  # .pyc files embed the source mtime
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
    }
)


def tree_hash(root: str | Path, *, excludes: frozenset[str] = DEFAULT_EXCLUDES) -> str:
    """Return a sha256 over the contents of `root`.

    Directories, regular files and symlinks are all recorded. Symlinks are
    hashed as their target text rather than followed, so a link pointing outside
    the tree changes the hash without reading anything outside it.

    Args:
        root: Directory to hash.
        excludes: Base names pruned wherever they appear in the tree.

    Raises:
        NotADirectoryError: If `root` is not an existing directory.
    """
    base = Path(root).resolve()
    if not base.is_dir():
        raise NotADirectoryError(f"not a directory: {base}")

    entries = sorted(_entries(base, excludes))

    digest = hashlib.sha256()
    for relative, payload in entries:
        # Length-prefixed so that no combination of names and payloads can be
        # rearranged into the same byte stream.
        name = relative.encode()
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(len(payload).to_bytes(4, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _entries(base: Path, excludes: frozenset[str]) -> list[tuple[str, bytes]]:
    found: list[tuple[str, bytes]] = []
    for dirpath, dirnames, filenames in os.walk(base, topdown=True, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in excludes]
        here = Path(dirpath)
        for name in [*dirnames, *filenames]:
            if name in excludes:
                continue
            path = here / name
            found.append((path.relative_to(base).as_posix(), _payload(path)))
    return found


def _payload(path: Path) -> bytes:
    if path.is_symlink():
        return b"l\0" + os.readlink(path).encode()
    if path.is_dir():
        return b"d"
    mode = b"x" if os.access(path, os.X_OK) else b"-"
    return b"f" + mode + hashlib.sha256(path.read_bytes()).digest()
