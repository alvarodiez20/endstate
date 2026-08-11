# CLI reference

```bash
endstate --help
```

## `endstate run`

Run the agent against a working directory.

```bash
endstate run PROMPT [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `PROMPT` | required unless `--resume` | What the agent should do. Omit it with `--resume` to finish an interrupted run instead of adding an instruction. |
| `--workdir`, `-w` | current directory | Sandbox directory. The only place tools may touch. |
| `--model`, `-m` | `gpt-4o-mini` | Model id. Names starting with `claude` route to Anthropic. |
| `--base-url` | — | OpenAI-compatible endpoint (vLLM, Ollama, a gateway) |
| `--max-steps` | `25` | Ceiling on model calls |
| `--max-context-tokens` | `128000` | Context budget, minus 8,000 reserved for output |
| `--prices` | — | Path to a JSON price table |
| `--resume` | — | Session id to resume. Without a prompt, outstanding tool calls are executed and the run continues. |

Prints the final message, then a summary: session id, steps, stop reason, input and output tokens,
compactions, denied calls, and cost if a price table was supplied.

**Exit code is 0 whenever the run completes**, including when the agent failed at the task. The loop
cannot know whether the job was done — see [The loop](../concepts/the-loop.md). Check the end state
yourself.

## `endstate sessions`

List stored session ids, newest first.

```bash
endstate sessions
```

Sessions live in `.endstate/sessions.sqlite3` relative to the working directory of the CLI.

## `endstate version`

```bash
endstate version
```

## Environment variables

| Variable | Used by |
| --- | --- |
| `OPENAI_API_KEY` | The OpenAI-compatible adapter, including gateways and self-hosted endpoints |
| `ANTHROPIC_API_KEY` | The Anthropic adapter (`--model claude-*`) |

## Examples

Fix a failing test in a scratch directory:

```bash
endstate run "the test in this directory fails, find out why and fix it" -w /tmp/demo
```

Point at a local vLLM server with an honest context window:

```bash
endstate run "add a --verbose flag to the CLI" -w ./sandbox --base-url http://localhost:8000/v1 --model Qwen/Qwen2.5-Coder-7B-Instruct --max-context-tokens 32768
```

Finish a run that was killed partway through:

```bash
endstate run --resume a3f9c211d4e0 -w /tmp/demo
```

Continue an earlier session with a new instruction and costs reported:

```bash
endstate run "now add a test for the edge case" --resume a3f9c211d4e0 -w /tmp/demo --prices ./prices.json
```
