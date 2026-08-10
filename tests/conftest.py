from pathlib import Path

import pytest

from endstate.agent.tools.base import ToolContext


@pytest.fixture
def workdir(tmp_path: Path) -> Path:
    (tmp_path / "hello.txt").write_text("hello world\n", encoding="utf-8")
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    return tmp_path


@pytest.fixture
def ctx(workdir: Path) -> ToolContext:
    return ToolContext(workdir=workdir, timeout_s=10.0)
