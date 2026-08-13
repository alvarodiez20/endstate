"""Command line interface."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

# Grader reasons and error text are data, not markup. A check named `/[a-z]+/`
# or a hint to `pip install 'endstate[openai]'` renders with the brackets eaten
# unless it is escaped on the way in.
from rich.markup import escape
from rich.table import Table

from endstate import __version__
from endstate.agent.context import ContextManager, TokenBudget
from endstate.agent.loop import AgentLoop
from endstate.agent.permissions import default_policy
from endstate.agent.session import SessionStore
from endstate.agent.tools import default_tools
from endstate.agent.tools.base import ToolContext
from endstate.evals import (
    DEFAULT_IMAGE,
    DockerSandbox,
    EvalRunner,
    LocalSandbox,
    Sandbox,
    Task,
    discover_tasks,
    docker_available,
    write_report,
)
from endstate.telemetry.cost import CostAccountant, PriceTable

app = typer.Typer(add_completion=False, help="Agent evals that grade the end state.")
console = Console()


def _provider(model: str, base_url: str | None):  # type: ignore[no-untyped-def]
    if model.startswith("claude"):
        from endstate.providers.anthropic import AnthropicProvider

        return AnthropicProvider(model=model)
    from endstate.providers.openai_compat import OpenAICompatProvider

    return OpenAICompatProvider(model=model, base_url=base_url, api_key=os.getenv("OPENAI_API_KEY"))


@app.command()
def version() -> None:
    """Print the version."""
    console.print(f"endstate {__version__}")


@app.command()
def run(
    prompt: str | None = typer.Argument(
        None, help="What the agent should do. Omit with --resume to finish an interrupted run."
    ),
    workdir: Path = typer.Option(Path.cwd(), "--workdir", "-w", help="Sandbox directory."),
    model: str = typer.Option("gpt-4o-mini", "--model", "-m"),
    base_url: str | None = typer.Option(None, "--base-url", help="OpenAI-compatible endpoint."),
    max_steps: int = typer.Option(25, "--max-steps"),
    max_context: int = typer.Option(128_000, "--max-context-tokens"),
    prices: Path | None = typer.Option(None, "--prices", help="JSON price table."),
    resume: str | None = typer.Option(None, "--resume", help="Session id to resume."),
) -> None:
    """Run the agent against a working directory."""
    if prompt is None and resume is None:
        raise typer.BadParameter("give a prompt, or --resume a session to continue it")

    store = SessionStore()
    session = store.resume(resume) if resume else store.create(model=model)
    accountant = CostAccountant(PriceTable.from_file(prices) if prices else None)

    loop = AgentLoop(
        provider=_provider(model, base_url),
        tools=default_tools(),
        tool_context=ToolContext(workdir=workdir),
        policy=default_policy(),
        context=ContextManager(budget=TokenBudget(max_context_tokens=max_context)),
        session=session,
        accountant=accountant,
        max_steps=max_steps,
    )

    # No prompt means "finish what you were doing": outstanding tool calls are
    # executed and the run carries on, rather than a new instruction being added.
    result = loop.resume() if prompt is None else loop.run(prompt)
    session.close()

    console.print(result.final_text or "(no final message)")

    table = Table(title="run", show_header=False)
    table.add_row("session", result.session_id or "-")
    table.add_row("steps", str(result.steps))
    table.add_row("stop reason", result.stop_reason.value)
    table.add_row("input tokens", f"{result.usage.input_tokens:,}")
    table.add_row("output tokens", f"{result.usage.output_tokens:,}")
    table.add_row("compactions", str(len(result.compaction_events)))
    table.add_row("denied calls", str(len(result.denied_calls)))
    if accountant.priced_models():
        table.add_row("cost (USD)", f"{accountant.total_cost():.4f}")
    elif accountant.unpriced_models():
        table.add_row("cost (USD)", "unknown (no price for model; pass --prices)")
    console.print(table)


@app.command()
# Shadows the builtin inside this module, which is not used here. The command is
# `endstate eval`, and renaming the function would rename the command.
def eval(
    suite: Path = typer.Option(Path("tasks"), "--suite", "-s", help="Directory of task folders."),
    model: str = typer.Option("gpt-4o-mini", "--model", "-m"),
    base_url: str | None = typer.Option(None, "--base-url", help="OpenAI-compatible endpoint."),
    sandbox: str = typer.Option("docker", "--sandbox", help="docker | local."),
    image: str = typer.Option(DEFAULT_IMAGE, "--image", help="Container image for the sandbox."),
    network: bool = typer.Option(False, "--network/--no-network", help="Let tasks reach the net."),
    jobs: int = typer.Option(1, "--jobs", "-j", help="Tasks to run concurrently."),
    only: list[str] = typer.Option([], "--task", "-t", help="Run only these task ids."),
    category: list[str] = typer.Option([], "--category", "-c", help="Run only these categories."),
    prices: Path | None = typer.Option(None, "--prices", help="JSON price table."),
    out: Path | None = typer.Option(None, "--out", help="Directory to write the report into."),
) -> None:
    """Run an eval suite and report on the end state of each sandbox."""
    tasks = discover_tasks(suite)
    if only:
        tasks = [t for t in tasks if t.id in set(only)]
    if category:
        tasks = [t for t in tasks if t.category in set(category)]
    if not tasks:
        raise typer.BadParameter(f"no tasks matched in {suite}")

    if sandbox == "docker" and not docker_available():
        raise typer.BadParameter(
            "docker is not reachable. Start it, or pass --sandbox local — which runs task "
            "commands on this machine with no isolation and is for development only."
        )

    price_table = PriceTable.from_file(prices) if prices else PriceTable()

    def make_sandbox(task: Task) -> Sandbox:
        if sandbox == "local":
            return LocalSandbox(task.fixture)
        return DockerSandbox(task.fixture, image=image, network=network)

    runner = EvalRunner(
        provider_factory=lambda task: _provider(model, base_url),
        sandbox_factory=make_sandbox,
        prices=price_table,
        jobs=jobs,
        provider_name="anthropic" if model.startswith("claude") else base_url or "openai",
        sandbox_name=f"{sandbox}:{image}" if sandbox == "docker" else "local",
        on_result=lambda r: console.print(
            f"[{'green' if r.passed else 'red'}]{'pass' if r.passed else 'fail'}[/] "
            f"{escape(r.task_id)} ({r.steps} steps, {r.wall_clock_s:.1f}s)"
        ),
    )
    result = runner.run_suite(tasks)

    table = Table(title=f"{escape(result.model or model)} · {len(result.results)} tasks")
    table.add_column("task")
    table.add_column("verdict")
    table.add_column("steps", justify="right")
    table.add_column("tokens", justify="right")
    for task_result in result.results:
        table.add_row(
            escape(task_result.task_id),
            "pass" if task_result.passed else f"fail — {escape(task_result.verdict.reason)}",
            str(task_result.steps),
            f"{task_result.usage.total_tokens:,}",
        )
    console.print(table)
    console.print(f"pass rate: {result.pass_rate:.0%}")

    if out is not None:
        markdown_path, json_path = write_report(result, out, price_table)
        console.print(f"wrote {markdown_path} and {json_path}")

    # A failing task is data. A harness error is a broken run, and exiting 0 on
    # one would let a suite that never really executed look like a clean sweep.
    if result.errored:
        for task_result in result.errored:
            console.print(
                f"[red]error[/] {escape(task_result.task_id)}: {escape(task_result.error)}"
            )
        raise typer.Exit(code=1)


@app.command()
def sessions() -> None:
    """List stored sessions."""
    for session_id in SessionStore().list_sessions():
        console.print(session_id)


if __name__ == "__main__":  # pragma: no cover
    app()
