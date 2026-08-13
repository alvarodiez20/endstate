"""The sandbox: what the agent gets, and what it is kept away from."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from endstate.evals.sandbox import (
    DOCKER_PROBE_TIMEOUT_S,
    DockerSandbox,
    ExecResult,
    LocalSandbox,
    SandboxError,
    docker_available,
    stage_tree,
    subprocess_runner,
)


@pytest.fixture
def fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture"
    (repo / "pkg").mkdir(parents=True)
    (repo / "pkg" / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    (repo / ".git").mkdir()
    (repo / ".git" / "config").write_text("[core]\n", encoding="utf-8")
    return repo


def test_setup_copies_the_fixture(fixture_repo: Path, tmp_path: Path) -> None:
    with LocalSandbox(fixture_repo, tmp_path / "box") as sandbox:
        assert sandbox.read_text("pkg/mod.py") == "VALUE = 1\n"
        assert sandbox.exists("README.md")


def test_git_history_is_not_shipped(fixture_repo: Path, tmp_path: Path) -> None:
    """A task built from a real repository ships the answer inside it."""
    with LocalSandbox(fixture_repo, tmp_path / "box") as sandbox:
        assert not sandbox.exists(".git")


def test_the_pristine_fixture_survives_the_agent(fixture_repo: Path, tmp_path: Path) -> None:
    with LocalSandbox(fixture_repo, tmp_path / "box") as sandbox:
        sandbox.write_text("pkg/mod.py", "VALUE = 99\n")
        assert sandbox.read_text("pkg/mod.py") == "VALUE = 99\n"
        assert sandbox.fixture_text("pkg/mod.py") == "VALUE = 1\n"


def test_missing_files_read_as_empty(fixture_repo: Path, tmp_path: Path) -> None:
    with LocalSandbox(fixture_repo, tmp_path / "box") as sandbox:
        assert sandbox.read_text("nope.py") == ""
        assert sandbox.fixture_text("nope.py") == ""


def test_paths_cannot_escape(fixture_repo: Path, tmp_path: Path) -> None:
    with LocalSandbox(fixture_repo, tmp_path / "box") as sandbox:
        with pytest.raises(SandboxError):
            sandbox.read_text("../secrets.txt")
        with pytest.raises(SandboxError):
            sandbox.fixture_text("../../etc/passwd")


def test_changed_paths_sees_additions_edits_and_deletions(
    fixture_repo: Path, tmp_path: Path
) -> None:
    with LocalSandbox(fixture_repo, tmp_path / "box") as sandbox:
        sandbox.write_text("pkg/mod.py", "VALUE = 2\n")
        sandbox.write_text("pkg/new.py", "x = 1\n")
        sandbox.path("README.md").unlink()
        assert sandbox.changed_paths() == ["README.md", "pkg/mod.py", "pkg/new.py"]


def test_seal_freezes_the_end_state_before_the_holdout_lands(
    fixture_repo: Path, tmp_path: Path
) -> None:
    """Otherwise every tree assertion is made against a tree the grader changed."""
    holdout = tmp_path / "holdout"
    (holdout / "tests").mkdir(parents=True)
    (holdout / "tests" / "test_extra.py").write_text("# held out\n", encoding="utf-8")

    with LocalSandbox(fixture_repo, tmp_path / "box") as sandbox:
        before = sandbox.seal()
        sandbox.stage(holdout)
        assert sandbox.exists("tests/test_extra.py")
        assert sandbox.tree_hash() == before
        assert "tests/test_extra.py" not in sandbox.end_state_files()
        assert "tests/test_extra.py" not in sandbox.changed_paths()


def test_tree_hash_is_live_until_sealed(fixture_repo: Path, tmp_path: Path) -> None:
    with LocalSandbox(fixture_repo, tmp_path / "box") as sandbox:
        before = sandbox.tree_hash()
        sandbox.write_text("pkg/mod.py", "VALUE = 3\n")
        assert sandbox.tree_hash() != before


def test_local_sandbox_runs_commands_in_the_tree(fixture_repo: Path, tmp_path: Path) -> None:
    with LocalSandbox(fixture_repo, tmp_path / "box") as sandbox:
        result = sandbox.run("cat pkg/mod.py")
        assert result.ok
        assert "VALUE = 1" in result.stdout


def test_local_sandbox_reports_failure(fixture_repo: Path, tmp_path: Path) -> None:
    with LocalSandbox(fixture_repo, tmp_path / "box") as sandbox:
        result = sandbox.run("exit 3")
        assert result.exit_code == 3
        assert not result.ok


def test_local_sandbox_times_out(fixture_repo: Path, tmp_path: Path) -> None:
    with LocalSandbox(fixture_repo, tmp_path / "box") as sandbox:
        result = sandbox.run("sleep 5", timeout_s=0.2)
        assert result.timed_out
        assert not result.ok


def test_the_temporary_tree_is_removed(fixture_repo: Path) -> None:
    with LocalSandbox(fixture_repo) as sandbox:
        workdir = sandbox.workdir
        assert workdir.is_dir()
    assert not workdir.exists()


def test_staging_a_missing_directory_is_an_error(fixture_repo: Path, tmp_path: Path) -> None:
    with LocalSandbox(fixture_repo, tmp_path / "box") as sandbox, pytest.raises(SandboxError):
        sandbox.stage(tmp_path / "nowhere")


def test_stage_overlays_rather_than_replaces(tmp_path: Path) -> None:
    source = tmp_path / "src"
    (source / "a").mkdir(parents=True)
    (source / "a" / "new.txt").write_text("new\n", encoding="utf-8")
    destination = tmp_path / "dst"
    (destination / "a").mkdir(parents=True)
    (destination / "a" / "kept.txt").write_text("kept\n", encoding="utf-8")

    stage_tree(source, destination)
    assert (destination / "a" / "kept.txt").exists()
    assert (destination / "a" / "new.txt").exists()


def test_exec_result_output_joins_both_streams() -> None:
    result = ExecResult(command="x", exit_code=1, stdout="out", stderr="err")
    assert result.output == "outerr"


# --- Docker ---------------------------------------------------------------
#
# The daemon is not assumed to exist, so these assert on the argv the sandbox
# builds. "network off by default" is a claim about a flag; this is where the
# flag is checked.


class FakeRunner:
    def __init__(self, *, container_id: str = "abc123", ok: bool = True) -> None:
        self.calls: list[list[str]] = []
        self.container_id = container_id
        self.ok = ok

    def __call__(self, argv: Sequence[str], timeout_s: float | None) -> ExecResult:
        self.calls.append(list(argv))
        if not self.ok:
            return ExecResult(command=" ".join(argv), exit_code=1, stderr="no daemon")
        if argv[:2] == ["docker", "run"]:
            return ExecResult(command=" ".join(argv), exit_code=0, stdout=self.container_id + "\n")
        return ExecResult(command=" ".join(argv), exit_code=0, stdout="ok")


def test_docker_runs_one_container_per_task_with_no_network(
    fixture_repo: Path, tmp_path: Path
) -> None:
    runner = FakeRunner()
    with DockerSandbox(fixture_repo, tmp_path / "box", runner=runner) as sandbox:
        sandbox.run("echo one")
        sandbox.run("echo two")

    starts = [c for c in runner.calls if c[:2] == ["docker", "run"]]
    execs = [c for c in runner.calls if c[:2] == ["docker", "exec"]]
    removals = [c for c in runner.calls if c[:2] == ["docker", "rm"]]

    assert len(starts) == 1, "one container per task, not one per command"
    assert len(execs) == 2
    assert len(removals) == 1

    start = starts[0]
    assert start[start.index("--network") + 1] == "none"
    assert "--rm" in start
    assert "--cap-drop" in start and start[start.index("--cap-drop") + 1] == "ALL"
    assert f"type=bind,src={sandbox.workdir},dst=/work" in start


def test_docker_network_can_be_opted_into(fixture_repo: Path, tmp_path: Path) -> None:
    box = DockerSandbox(fixture_repo, tmp_path / "box", network=True, runner=FakeRunner())
    argv = box.start_argv()
    assert argv[argv.index("--network") + 1] == "bridge"


def test_docker_exec_reports_the_model_s_command(fixture_repo: Path, tmp_path: Path) -> None:
    """Not the docker invocation, which the model neither wrote nor can fix."""
    with DockerSandbox(fixture_repo, tmp_path / "box", runner=FakeRunner()) as sandbox:
        assert sandbox.run("pytest -q").command == "pytest -q"


def test_docker_failure_to_start_is_a_sandbox_error(fixture_repo: Path, tmp_path: Path) -> None:
    box = DockerSandbox(fixture_repo, tmp_path / "box", runner=FakeRunner(ok=False))
    with pytest.raises(SandboxError, match="could not start container"), box:
        pass


def test_docker_start_with_no_container_id_is_an_error(fixture_repo: Path, tmp_path: Path) -> None:
    box = DockerSandbox(fixture_repo, tmp_path / "box", runner=FakeRunner(container_id=""))
    with pytest.raises(SandboxError, match="no container id"), box:
        pass


def test_docker_refuses_to_run_before_it_is_started(fixture_repo: Path, tmp_path: Path) -> None:
    box = DockerSandbox(fixture_repo, tmp_path / "box", runner=FakeRunner())
    with pytest.raises(SandboxError, match="not started"):
        box.run("echo hi")


def test_docker_available_reflects_the_runner() -> None:
    assert docker_available(FakeRunner()) is True
    assert docker_available(FakeRunner(ok=False)) is False


def test_the_availability_probe_does_not_block() -> None:
    """It gates the CLI, so an unreachable daemon must fail fast, not hang.

    Five seconds is already generous for a command a healthy daemon answers in
    milliseconds, and every case that takes longer is one where the answer is
    False anyway.
    """
    seen: list[float | None] = []

    def record(argv: Sequence[str], timeout_s: float | None) -> ExecResult:
        seen.append(timeout_s)
        return ExecResult(command=" ".join(argv), exit_code=0, stdout="29.7.2")

    docker_available(record)
    assert seen == [DOCKER_PROBE_TIMEOUT_S]
    assert DOCKER_PROBE_TIMEOUT_S <= 5.0


def test_docker_available_is_false_without_the_binary() -> None:
    def missing(argv: Sequence[str], timeout_s: float | None) -> ExecResult:
        raise SandboxError("docker is not installed")

    assert docker_available(missing) is False


def test_subprocess_runner_reports_a_missing_binary() -> None:
    with pytest.raises(SandboxError, match="not installed"):
        subprocess_runner(["endstate-definitely-not-a-binary"], 5.0)


def test_subprocess_runner_times_out() -> None:
    assert subprocess_runner(["sleep", "5"], 0.2).timed_out


# --- against a real daemon ------------------------------------------------
#
# Everything above asserts on the argv, which is where "network off by default"
# is decided but not where it is proved. These need Docker, so they skip on a
# machine without it and run in CI, which has one.
#
# The probe is held in a module-level constant rather than called inside each
# decorator: `skipif` conditions are evaluated at import, so one call per
# decorator means paying the probe timeout once per test on any machine where
# the daemon is missing or wedged.
DOCKER = docker_available()
needs_docker = pytest.mark.skipif(not DOCKER, reason="no Docker daemon")


@needs_docker
def test_docker_really_isolates_and_really_mounts(fixture_repo: Path) -> None:
    with DockerSandbox(fixture_repo) as sandbox:
        assert sandbox.run("cat pkg/mod.py").stdout.strip() == "VALUE = 1"

        # The claim the whole sandbox rests on.
        reached = sandbox.run(
            "python -c \"import socket; socket.create_connection(('1.1.1.1', 80), 3)\""
        )
        assert reached.exit_code != 0, "the sandbox reached the network"

        # The mount is one filesystem seen from two sides: the container writes,
        # the host-side file tools and the grader read.
        sandbox.run("echo written-inside > made_in_container.txt")
        assert sandbox.read_text("made_in_container.txt") == "written-inside\n"

        sandbox.write_text("pkg/mod.py", "VALUE = 2\n")
        assert sandbox.run("cat pkg/mod.py").stdout.strip() == "VALUE = 2"

        assert sandbox.changed_paths() == ["made_in_container.txt", "pkg/mod.py"]


@needs_docker
def test_the_container_is_gone_afterwards(fixture_repo: Path) -> None:
    with DockerSandbox(fixture_repo) as sandbox:
        container_id = sandbox.container_id
        assert container_id is not None
    still_there = subprocess_runner(["docker", "ps", "-aq", "--filter", f"id={container_id}"], 30.0)
    assert still_there.stdout.strip() == "", "the container outlived the task"
