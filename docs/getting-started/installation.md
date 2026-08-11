# Installation

## Install

=== "pip"

    ```bash
    pip install endstate
    ```

=== "uv"

    ```bash
    uv pip install endstate
    ```

=== "pipx (CLI only)"

    ```bash
    pipx install endstate
    ```

Requires Python 3.11 or newer. Verify:

```bash
endstate version
```

## Provider extras

The core package has no provider SDKs. Install the one you need:

=== "OpenAI-compatible"

    ```bash
    pip install "endstate[openai]"
    ```

    Covers the OpenAI API and anything that speaks its protocol — vLLM, Ollama, LiteLLM, most
    gateways. See [Use a self-hosted model](../guides/self-hosted-models.md).

=== "Anthropic"

    ```bash
    pip install "endstate[anthropic]"
    ```

=== "Both"

    ```bash
    pip install "endstate[all]"
    ```

This split is deliberate: a harness that drags two SDKs into your environment to run one of them is
being rude about your dependency tree. The [provider Protocol](../concepts/messages-and-providers.md)
means neither is imported unless used.

## Credentials

Set the key for whichever provider you are pointing at:

```bash
export OPENAI_API_KEY=sk-...
```

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Model names starting with `claude` route to the Anthropic adapter; everything else goes to the
OpenAI-compatible one.

## From source

```bash
git clone https://github.com/alvarodiez20/endstate
cd endstate
uv sync --group dev
```

Run the checks the way CI does:

```bash
make check
```

That runs `ruff check`, `ruff format --check`, `mypy --strict` and `pytest`. The whole suite runs in
under a second — no network, no API key, no cost — because everything is tested against
[`FakeProvider`](../concepts/messages-and-providers.md).

## Next

[Your first run →](first-run.md)
