"""The eval sandbox: one disposable container per task.

Decision **D7**. Three reasons, in order of importance: determinism (a shared
sandbox means task 7 sees whatever task 6 left behind), parallelism, and the
fact that a container is the only reason it is sane to hand an agent a shell.

The shape here is deliberate. A sandbox owns a *live tree* on the host — a copy
of the task fixture — and a way to execute commands against it. The tree is bind
mounted into the container, so the file tools write host-side into the same
bytes the shell sees container-side, and the grader can hash the result without
copying anything back out.

Two things are sealed off from the agent on purpose:

*The pristine fixture.* Kept beside the live tree so a grader can ask "is this
file byte-for-byte what we shipped?" — the assertion that catches an agent
editing the tests instead of the code.

*Version control history.* `.git` is not copied. A task built from a real
repository ships the answer inside it, and `git log` is a cheaper path to a
passing grade than solving the problem. This is runtime contamination, and it is
measured in the wild at a scale that makes it the default rather than an option.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

from endstate.agent.tools.base import confine
from endstate.tree import DEFAULT_EXCLUDES, tree_hash

STAGING_EXCLUDES = frozenset(
    {
        ".git",  # the answer, for any task built from a real repository
        ".hg",
        ".svn",
        ".endstate",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".venv",
        "node_modules",
    }
)

DEFAULT_IMAGE = "python:3.12-slim"


class SandboxError(RuntimeError):
    """Raised when the sandbox itself fails, as distinct from the task failing."""


@dataclass(frozen=True)
class ExecResult:
    """The outcome of one command run inside the sandbox."""

    command: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    @property
    def output(self) -> str:
        """stdout and stderr, in the order a terminal would have shown them."""
        return "".join(part for part in (self.stdout, self.stderr) if part)


CommandRunner = Callable[[Sequence[str], float | None], ExecResult]
"""Runs an argv on the host. Injected so the Docker plumbing is testable."""


def subprocess_runner(argv: Sequence[str], timeout_s: float | None) -> ExecResult:
    printable = " ".join(argv)
    try:
        proc = subprocess.run(  # noqa: S603 - argv is built here, never user text
            list(argv), capture_output=True, text=True, timeout=timeout_s
        )
    except subprocess.TimeoutExpired:
        return ExecResult(command=printable, exit_code=124, timed_out=True)
    except FileNotFoundError as exc:
        raise SandboxError(f"{argv[0]} is not installed or not on PATH") from exc
    return ExecResult(
        command=printable, exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
    )


def stage_tree(
    source: Path, destination: Path, *, excludes: frozenset[str] = STAGING_EXCLUDES
) -> None:
    """Copy `source` over `destination`, pruning `excludes` at every level.

    Overlays rather than replaces: staging held-out tests into a tree the agent
    has already worked in must not delete the agent's work.
    """
    source = Path(source)
    if not source.is_dir():
        raise SandboxError(f"not a directory: {source}")
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        symlinks=True,
        ignore=lambda _dir, names: {n for n in names if n in excludes},
    )


class Sandbox(ABC):
    """A disposable working tree plus a way to run commands against it.

    Subclasses supply execution only; everything filesystem-shaped is here, so
    the Docker and local backends cannot drift on what a grader observes.
    """

    def __init__(
        self,
        fixture: Path,
        root: Path | None = None,
        *,
        default_timeout_s: float = 120.0,
        excludes: frozenset[str] = STAGING_EXCLUDES,
    ) -> None:
        self.fixture = Path(fixture).resolve()
        self.default_timeout_s = default_timeout_s
        self.excludes = excludes
        self._tempdir: tempfile.TemporaryDirectory[str] | None = None
        if root is None:
            self._tempdir = tempfile.TemporaryDirectory(prefix="endstate-task-")
            root = Path(self._tempdir.name)
        self.workdir = Path(root).resolve()
        self._sealed_hash: str | None = None
        self._sealed_files: dict[str, str] | None = None

    # --- lifecycle --------------------------------------------------------

    def setup(self) -> None:
        """Materialise the fixture into the live tree."""
        stage_tree(self.fixture, self.workdir, excludes=self.excludes)

    def start(self) -> None:  # noqa: B027 - optional hook; a local sandbox has nothing to start
        """Bring up whatever executes commands. Nothing to do by default."""

    def close(self) -> None:
        """Tear down execution and, if we own it, the live tree."""
        if self._tempdir is not None:
            self._tempdir.cleanup()
            self._tempdir = None

    def __enter__(self) -> Sandbox:
        self.setup()
        try:
            self.start()
        except Exception:
            self.close()
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # --- execution --------------------------------------------------------

    @abstractmethod
    def run(self, command: str, *, timeout_s: float | None = None) -> ExecResult:
        """Run a shell command with the live tree as the working directory."""

    # --- reading the end state -------------------------------------------

    def path(self, relative: str) -> Path:
        """Resolve a path inside the live tree, refusing anything that escapes.

        Raises:
            SandboxError: If the path points outside the sandbox.
        """
        try:
            return confine(self.workdir, relative)
        except ValueError as exc:
            raise SandboxError(str(exc)) from exc

    def exists(self, relative: str) -> bool:
        return self.path(relative).exists()

    def read_text(self, relative: str) -> str:
        """Read a file from the live tree, or return '' if it is not there.

        Missing is not an error: a grader asking "does this file still contain
        the secret?" wants False for a deleted file, not an exception.
        """
        target = self.path(relative)
        if not target.is_file():
            return ""
        return target.read_text(encoding="utf-8", errors="replace")

    def write_text(self, relative: str, content: str) -> None:
        target = self.path(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def fixture_text(self, relative: str) -> str:
        """Read a file as it was shipped, before the agent touched anything."""
        try:
            original = confine(self.fixture, relative)
        except ValueError as exc:
            raise SandboxError(str(exc)) from exc
        if not original.is_file():
            return ""
        return original.read_text(encoding="utf-8", errors="replace")

    def stage(self, source: Path) -> None:
        """Overlay a directory into the live tree. Used for held-out tests."""
        stage_tree(source, self.workdir, excludes=self.excludes)

    def seal(self) -> str:
        """Freeze the agent's end state and return its hash.

        Called once the agent has stopped and before anything is staged in for
        grading. Held-out tests are files too: without a seal, copying them in
        would change the very tree hash the graders are about to assert on.
        """
        if self._sealed_hash is None:
            self._sealed_hash = tree_hash(self.workdir, excludes=DEFAULT_EXCLUDES)
            self._sealed_files = _file_texts(self.workdir, self.excludes)
        return self._sealed_hash

    def tree_hash(self) -> str:
        """The end-state hash: sealed if the run is over, live if it is not."""
        if self._sealed_hash is not None:
            return self._sealed_hash
        return tree_hash(self.workdir, excludes=DEFAULT_EXCLUDES)

    def end_state_files(self) -> dict[str, str]:
        """Every text file in the end state, keyed by relative path."""
        if self._sealed_files is not None:
            return dict(self._sealed_files)
        return _file_texts(self.workdir, self.excludes)

    def changed_paths(self) -> list[str]:
        """Relative paths whose content differs from the fixture.

        Includes files the agent added and files it deleted, because "deleted
        something inconvenient" is one of the things end-state grading exists to
        catch.
        """
        before = _file_texts(self.fixture, self.excludes)
        after = self.end_state_files()
        return sorted({p for p in set(before) | set(after) if before.get(p) != after.get(p)})


def _file_texts(root: Path, excludes: frozenset[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    if not root.is_dir():
        return texts
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in excludes and d not in DEFAULT_EXCLUDES)
        here = Path(dirpath)
        for name in sorted(filenames):
            if name in excludes:
                continue
            path = here / name
            if path.is_symlink() or not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            texts[relative] = path.read_text(encoding="utf-8", errors="replace")
    return texts


class LocalSandbox(Sandbox):
    """Runs commands as subprocesses on the host, in the live tree.

    **This is not an isolation boundary.** It exists so the runner, the graders
    and the task suite can be tested on a machine without Docker, and so a task
    can be debugged without a container in the way. Real benchmark runs use
    `DockerSandbox`; anything published from a `LocalSandbox` run should say so.
    """

    def run(self, command: str, *, timeout_s: float | None = None) -> ExecResult:
        env = dict(os.environ)
        # Byte-compilation writes __pycache__ into the tree being hashed, and
        # hash randomisation is a determinism leak in anything that iterates a set.
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONHASHSEED"] = "0"
        try:
            proc = subprocess.run(  # noqa: S602 - the sandbox is the point
                command,
                shell=True,
                cwd=str(self.workdir),
                capture_output=True,
                text=True,
                timeout=timeout_s if timeout_s is not None else self.default_timeout_s,
                env=env,
            )
        except subprocess.TimeoutExpired:
            return ExecResult(command=command, exit_code=124, timed_out=True)
        return ExecResult(
            command=command,
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )


class DockerSandbox(Sandbox):
    """One container per task, with the live tree bind mounted into it.

    The container is started once and held open with `tail -f /dev/null`, then
    every command runs through `docker exec`. Starting a fresh container per
    command would be a different guarantee — and a slower one — because a task's
    commands would no longer share process state.

    Defaults are the restrictive ones: no network, all capabilities dropped, no
    privilege escalation, capped memory and pids. Network is the interesting one.
    It is off because the fix for most benchmark tasks is a web search away, and
    an agent that retrieves the answer has not demonstrated it can derive it.
    """

    def __init__(
        self,
        fixture: Path,
        root: Path | None = None,
        *,
        image: str = DEFAULT_IMAGE,
        network: bool = False,
        memory: str = "2g",
        cpus: str = "2.0",
        pids_limit: int = 512,
        container_workdir: str = "/work",
        runner: CommandRunner | None = None,
        startup_timeout_s: float = 120.0,
        default_timeout_s: float = 120.0,
        excludes: frozenset[str] = STAGING_EXCLUDES,
    ) -> None:
        super().__init__(fixture, root, default_timeout_s=default_timeout_s, excludes=excludes)
        self.image = image
        self.network = network
        self.memory = memory
        self.cpus = cpus
        self.pids_limit = pids_limit
        self.container_workdir = container_workdir
        self.startup_timeout_s = startup_timeout_s
        self._runner: CommandRunner = runner or subprocess_runner
        self.container_id: str | None = None

    def start_argv(self) -> list[str]:
        """The `docker run` argv. Public because it is worth asserting on."""
        argv = [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--network",
            "bridge" if self.network else "none",
            "--workdir",
            self.container_workdir,
            "--mount",
            f"type=bind,src={self.workdir},dst={self.container_workdir}",
            "--memory",
            self.memory,
            "--cpus",
            self.cpus,
            "--pids-limit",
            str(self.pids_limit),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--env",
            "PYTHONDONTWRITEBYTECODE=1",
            "--env",
            "PYTHONHASHSEED=0",
        ]
        # Without this the container writes as root and the host-side grader
        # cannot read — or clean up — what the agent left behind.
        if hasattr(os, "getuid"):
            argv += ["--user", f"{os.getuid()}:{os.getgid()}"]
        argv += [self.image, "tail", "-f", "/dev/null"]
        return argv

    def start(self) -> None:
        result = self._runner(self.start_argv(), self.startup_timeout_s)
        if not result.ok:
            raise SandboxError(f"could not start container from {self.image!r}: {result.output}")
        self.container_id = result.stdout.strip()
        if not self.container_id:
            raise SandboxError("docker run returned no container id")

    def run(self, command: str, *, timeout_s: float | None = None) -> ExecResult:
        if self.container_id is None:
            raise SandboxError("sandbox is not started")
        argv = [
            "docker",
            "exec",
            "--workdir",
            self.container_workdir,
            self.container_id,
            "sh",
            "-c",
            command,
        ]
        result = self._runner(argv, timeout_s if timeout_s is not None else self.default_timeout_s)
        # Report the command the model asked for, not the docker invocation.
        return ExecResult(
            command=command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            timed_out=result.timed_out,
        )

    def close(self) -> None:
        if self.container_id is not None:
            self._runner(["docker", "rm", "--force", self.container_id], 60.0)
            self.container_id = None
        super().close()


def docker_available(runner: CommandRunner | None = None) -> bool:
    """Whether a usable Docker daemon is reachable."""
    run = runner or subprocess_runner
    try:
        return run(["docker", "version", "--format", "{{.Server.Version}}"], 20.0).ok
    except SandboxError:
        return False
