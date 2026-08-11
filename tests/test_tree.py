import os
from pathlib import Path

import pytest

from endstate.tree import tree_hash


def make(root: Path, files: dict[str, str]) -> Path:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


def test_identical_trees_hash_equal(tmp_path: Path) -> None:
    a = make(tmp_path / "a", {"x.txt": "one", "pkg/y.py": "two"})
    b = make(tmp_path / "b", {"x.txt": "one", "pkg/y.py": "two"})
    assert tree_hash(a) == tree_hash(b)


def test_hash_is_stable_across_calls(tmp_path: Path) -> None:
    root = make(tmp_path, {"x.txt": "one"})
    assert tree_hash(root) == tree_hash(root)


def test_content_change_changes_hash(tmp_path: Path) -> None:
    root = make(tmp_path, {"x.txt": "one"})
    before = tree_hash(root)
    (root / "x.txt").write_text("two", encoding="utf-8")
    assert tree_hash(root) != before


def test_new_file_changes_hash(tmp_path: Path) -> None:
    root = make(tmp_path, {"x.txt": "one"})
    before = tree_hash(root)
    (root / "z.txt").write_text("", encoding="utf-8")
    assert tree_hash(root) != before


def test_new_empty_directory_changes_hash(tmp_path: Path) -> None:
    root = make(tmp_path, {"x.txt": "one"})
    before = tree_hash(root)
    (root / "emptydir").mkdir()
    assert tree_hash(root) != before


def test_rename_changes_hash(tmp_path: Path) -> None:
    root = make(tmp_path, {"x.txt": "one"})
    before = tree_hash(root)
    (root / "x.txt").rename(root / "y.txt")
    assert tree_hash(root) != before


def test_mtime_does_not_change_hash(tmp_path: Path) -> None:
    root = make(tmp_path, {"x.txt": "one"})
    before = tree_hash(root)
    os.utime(root / "x.txt", (0, 0))
    assert tree_hash(root) == before


def test_executable_bit_changes_hash(tmp_path: Path) -> None:
    root = make(tmp_path, {"run.sh": "echo hi"})
    before = tree_hash(root)
    (root / "run.sh").chmod(0o755)
    assert tree_hash(root) != before


def test_excluded_directories_are_ignored(tmp_path: Path) -> None:
    root = make(tmp_path, {"x.txt": "one"})
    before = tree_hash(root)
    (root / ".git").mkdir()
    (root / ".git" / "HEAD").write_text("ref: refs/heads/main", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "m.pyc").write_bytes(b"\x00\x01")
    assert tree_hash(root) == before


def test_excludes_are_configurable(tmp_path: Path) -> None:
    root = make(tmp_path, {"x.txt": "one", "build/out.o": "junk"})
    assert tree_hash(root, excludes=frozenset({"build"})) != tree_hash(root)


def test_symlink_is_recorded_not_followed(tmp_path: Path) -> None:
    root = make(tmp_path, {"real.txt": "content"})
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("secret", encoding="utf-8")
    (root / "link").symlink_to(outside)

    before = tree_hash(root)
    outside.write_text("changed", encoding="utf-8")
    # The link's target text is unchanged, so the hash is too: the tree never
    # reads through the link.
    assert tree_hash(root) == before


def test_symlink_target_change_changes_hash(tmp_path: Path) -> None:
    root = make(tmp_path, {"a.txt": "a", "b.txt": "b"})
    (root / "link").symlink_to(root / "a.txt")
    before = tree_hash(root)
    (root / "link").unlink()
    (root / "link").symlink_to(root / "b.txt")
    assert tree_hash(root) != before


def test_path_and_content_cannot_be_confused(tmp_path: Path) -> None:
    """Length-prefixing keeps names and payloads from being rearranged."""
    a = make(tmp_path / "a", {"ab": "c", "d": "e"})
    b = make(tmp_path / "b", {"a": "bc", "d": "e"})
    assert tree_hash(a) != tree_hash(b)


def test_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        tree_hash(tmp_path / "nope")


def test_file_instead_of_directory_raises(tmp_path: Path) -> None:
    target = tmp_path / "f.txt"
    target.write_text("x", encoding="utf-8")
    with pytest.raises(NotADirectoryError):
        tree_hash(target)


def test_excluded_name_as_a_file_is_ignored(tmp_path: Path) -> None:
    """Git worktrees and submodules use a `.git` file, not a directory."""
    root = make(tmp_path, {"x.txt": "one"})
    before = tree_hash(root)
    (root / ".git").write_text("gitdir: ../.git/modules/thing", encoding="utf-8")
    assert tree_hash(root) == before
