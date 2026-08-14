"""Graders, and the contract that keeps them honest."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from endstate.evals.graders import (
    GraderContractError,
    changed_paths_within,
    command_succeeds,
    compose,
    file_contains,
    file_matches,
    files_unchanged,
    grader_for,
    no_new_skips,
    paths_absent,
    paths_exist,
    pattern_count,
    resolve,
)
from endstate.evals.sandbox import LocalSandbox, Sandbox
from endstate.evals.task import Check, GraderSpec, Verdict


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "mod.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_mod.py").write_text(
        "import unittest\n\n\nclass T(unittest.TestCase):\n    def test_add(self):\n"
        "        from pkg.mod import add\n\n        self.assertEqual(add(1, 2), 3)\n",
        encoding="utf-8",
    )
    return repo


@pytest.fixture
def sandbox(fixture_repo: Path, tmp_path: Path) -> Any:
    with LocalSandbox(fixture_repo, tmp_path / "box") as box:
        yield box


# --- the contract ---------------------------------------------------------


def grades_fine(sandbox: Sandbox, *, flag: bool = True) -> Verdict:
    return Verdict.ok()


def reads_the_transcript(sandbox: Sandbox, *, messages: list[str]) -> Verdict:
    return Verdict.ok()  # pragma: no cover - rejected before it can run


def wrong_first_parameter(box: Sandbox) -> Verdict:
    return Verdict.ok()  # pragma: no cover


def takes_nothing() -> Verdict:
    return Verdict.ok()  # pragma: no cover


def swallows_anything(sandbox: Sandbox, **kwargs: object) -> Verdict:
    return Verdict.ok()  # pragma: no cover


def sandbox_keyword_only(*, sandbox: Sandbox) -> Verdict:
    return Verdict.ok()  # pragma: no cover


def test_a_conforming_grader_resolves() -> None:
    grade = resolve(GraderSpec(name=f"{__name__}:grades_fine", args={"flag": False}))
    assert grade.__name__ == "grades_fine"


def test_a_grader_that_could_read_the_transcript_is_rejected() -> None:
    """The design decision the project turns on, enforced rather than trusted."""
    with pytest.raises(GraderContractError, match="never the transcript"):
        resolve(GraderSpec(name=f"{__name__}:reads_the_transcript"))


def test_the_first_parameter_must_be_the_sandbox() -> None:
    with pytest.raises(GraderContractError, match="must take `sandbox` first"):
        resolve(GraderSpec(name=f"{__name__}:wrong_first_parameter"))


def test_a_grader_must_take_a_sandbox_at_all() -> None:
    with pytest.raises(GraderContractError, match="no sandbox argument"):
        resolve(GraderSpec(name=f"{__name__}:takes_nothing"))


def test_kwargs_defeat_the_check_and_are_refused() -> None:
    with pytest.raises(GraderContractError, match=r"\*\*kwargs"):
        resolve(GraderSpec(name=f"{__name__}:swallows_anything"))


def test_the_sandbox_must_be_positional() -> None:
    with pytest.raises(GraderContractError, match="positionally"):
        resolve(GraderSpec(name=f"{__name__}:sandbox_keyword_only"))


def test_unimportable_and_missing_targets() -> None:
    with pytest.raises(GraderContractError, match="cannot import"):
        resolve(GraderSpec(name="endstate.no_such_module:grade"))
    with pytest.raises(GraderContractError, match="not a callable"):
        resolve(GraderSpec(name="endstate.evals.graders:no_such_function"))
    with pytest.raises(GraderContractError, match="not a 'module:function' path"):
        resolve(GraderSpec(name="bare"))


def test_dotted_paths_work_too() -> None:
    assert resolve(GraderSpec(name=f"{__name__}.grades_fine")) is not None


# --- the library ----------------------------------------------------------


def test_command_succeeds(sandbox: Sandbox) -> None:
    assert command_succeeds(sandbox, command="true").passed
    failed = command_succeeds(sandbox, command="echo boom; exit 2")
    assert not failed.passed
    assert "boom" in failed.checks[0].detail


def test_command_succeeds_can_expect_a_failure(sandbox: Sandbox) -> None:
    assert command_succeeds(sandbox, command="exit 7", expect_exit_code=7).passed


def test_command_that_times_out_fails(sandbox: Sandbox) -> None:
    verdict = command_succeeds(sandbox, command="sleep 5", timeout_s=0.2)
    assert not verdict.passed
    assert "timed out" in verdict.checks[0].detail


def test_files_unchanged_catches_an_edited_test(sandbox: Sandbox) -> None:
    """The single most common way a coding benchmark measures nothing."""
    assert files_unchanged(sandbox, paths=["tests/test_mod.py"]).passed
    sandbox.write_text("tests/test_mod.py", "# hah\n")
    verdict = files_unchanged(sandbox, paths=["tests/test_mod.py"])
    assert not verdict.passed
    assert verdict.checks[0].detail == "modified"


def test_files_unchanged_catches_a_deleted_test(sandbox: Sandbox) -> None:
    sandbox.path("tests/test_mod.py").unlink()
    verdict = files_unchanged(sandbox, paths=["tests/test_mod.py"])
    assert not verdict.passed
    assert verdict.checks[0].detail == "deleted or emptied"


def test_paths_exist_and_absent(sandbox: Sandbox) -> None:
    assert paths_exist(sandbox, paths=["pkg/mod.py"]).passed
    assert not paths_exist(sandbox, paths=["pkg/nope.py"]).passed
    assert paths_absent(sandbox, paths=["pkg/nope.py"]).passed
    assert not paths_absent(sandbox, paths=["pkg/mod.py"]).passed


def test_file_matches_both_ways(sandbox: Sandbox) -> None:
    assert file_matches(sandbox, path="pkg/mod.py", pattern=r"def add").passed
    assert file_matches(sandbox, path="pkg/mod.py", pattern=r"import os", should_match=False).passed


def test_file_contains(sandbox: Sandbox) -> None:
    assert file_contains(sandbox, path="pkg/mod.py", text="return a - b").passed
    assert file_contains(sandbox, path="pkg/mod.py", text="TODO", should_contain=False).passed


def test_pattern_count_bounds(sandbox: Sandbox) -> None:
    sandbox.write_text("pkg/a.py", "X = 1\nX = 2\n")
    assert pattern_count(sandbox, pattern=r"^X = ", paths=["pkg/a.py"], maximum=2).passed
    assert not pattern_count(sandbox, pattern=r"^X = ", paths=["pkg/a.py"], maximum=1).passed
    assert pattern_count(sandbox, pattern=r"^X = ", paths=["pkg/a.py"], minimum=2).passed
    assert not pattern_count(sandbox, pattern=r"^X = ", paths=["pkg/a.py"], minimum=3).passed


def test_pattern_count_globs_the_end_state(sandbox: Sandbox) -> None:
    sandbox.write_text("pkg/b.py", "import re\n")
    sandbox.write_text("pkg/c.py", "import re\n")
    verdict = pattern_count(sandbox, pattern=r"^import re", glob="pkg/*.py", maximum=1)
    assert not verdict.passed
    assert "found 2" in verdict.checks[0].detail


def test_pattern_count_with_no_bounds_passes(sandbox: Sandbox) -> None:
    assert pattern_count(sandbox, pattern="anything", paths=[]).passed


def test_no_new_skips_catches_a_smuggled_marker(sandbox: Sandbox) -> None:
    """Green because the test never ran is the cheapest exploit of all."""
    assert no_new_skips(sandbox).passed
    original = sandbox.read_text("tests/test_mod.py")
    sandbox.write_text(
        "tests/test_mod.py",
        original.replace("    def test_add", "    @unittest.skip('x')\n    def test_add"),
    )
    verdict = no_new_skips(sandbox)
    assert not verdict.passed
    assert "tests/test_mod.py" in verdict.checks[0].detail


def test_changed_paths_within_catches_collateral_damage(sandbox: Sandbox) -> None:
    sandbox.write_text("pkg/mod.py", "def add(a, b):\n    return a + b\n")
    assert changed_paths_within(sandbox, allowed=["pkg/*"]).passed
    sandbox.path("tests/test_mod.py").unlink()
    verdict = changed_paths_within(sandbox, allowed=["pkg/*"])
    assert not verdict.passed
    assert "tests/test_mod.py" in verdict.checks[0].detail


# --- composition ----------------------------------------------------------


def test_compose_is_a_conjunction_that_keeps_every_check(sandbox: Sandbox) -> None:
    grade = compose(
        [
            lambda s: Verdict.from_checks([Check(name="one", passed=True)]),
            lambda s: Verdict.from_checks([Check(name="two", passed=False)]),
            lambda s: Verdict.from_checks([Check(name="three", passed=True)]),
        ]
    )
    verdict = grade(sandbox)
    assert not verdict.passed
    assert len(verdict.checks) == 3
    assert verdict.reason == "two"


def test_grader_for_binds_arguments(sandbox: Sandbox) -> None:
    grade = grader_for(
        [GraderSpec(name="endstate.evals.graders:paths_exist", args={"paths": ["pkg/mod.py"]})]
    )
    assert grade(sandbox).passed


def test_verdict_helpers() -> None:
    assert Verdict.ok("fine").passed
    assert not Verdict.fail("nope").passed
    merged = Verdict.from_checks([Check(name="a", passed=True)]).merged_with(
        Verdict.from_checks([Check(name="b", passed=False)])
    )
    assert not merged.passed
    assert [c.name for c in merged.failed_checks] == ["b"]
    assert str(Check(name="a", passed=True)) == "[pass] a"
    assert str(Check(name="a", passed=False, detail="why")) == "[FAIL] a: why"


def test_merging_keeps_a_failure_that_carries_no_checks() -> None:
    """A grader that raised fails with a reason and an empty check list.

    Recomputing `passed` from the merged checks would read that empty list as
    "nothing failed" and turn a hard grader error into a pass — silently, and in
    the one direction that matters.
    """
    raised = Verdict.fail("grader raised TypeError: missing 'paths'")
    fine = Verdict.from_checks([Check(name="denied calls is at least 1", passed=True)])

    assert not raised.merged_with(fine).passed
    assert not fine.merged_with(raised).passed
    assert "TypeError" in raised.merged_with(fine).reason


def test_merging_two_passes_still_passes() -> None:
    left = Verdict.from_checks([Check(name="a", passed=True)])
    right = Verdict.from_checks([Check(name="b", passed=True)])
    merged = left.merged_with(right)
    assert merged.passed
    assert [c.name for c in merged.checks] == ["a", "b"]


def test_merging_names_every_failed_check_once() -> None:
    left = Verdict.from_checks([Check(name="a", passed=False)])
    right = Verdict.from_checks([Check(name="b", passed=False)])
    assert left.merged_with(right).reason == "a; b"
