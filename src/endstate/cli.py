"""Command line interface."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from endstate import __version__
from endstate.agent.context import ContextManager, TokenBudget
from endstate.agent.loop import AgentLoop
from endstate.agent.permissions import default_policy
from endstate.agent.session import SessionStore
from endstate.agent.tools import default_tools
from endstate.agent.tools.base import ToolContext
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
def sessions() -> None:
    """List stored sessions."""
    for session_id in SessionStore().list_sessions():
        console.print(session_id)


if __name__ == "__main__":  # pragma: no cover
    app()
