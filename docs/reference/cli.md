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

## `endstate eval`

Run a suite of tasks and grade the end state of each sandbox.

```bash
endstate eval --suite tasks/ [OPTIONS]
```

| Option | Default | Description |
| --- | --- | --- |
| `--suite`, `-s` | `tasks` | Directory of task folders. Every `task.json` beneath it is a task. |
| `--model`, `-m` | `gpt-4o-mini` | Model id. Names starting with `claude` route to Anthropic. |
| `--base-url` | — | OpenAI-compatible endpoint |
| `--sandbox` | `docker` | `docker` or `local`. See the warning below. |
| `--image` | `python:3.12-slim` | Container image, for the Docker sandbox |
| `--network` / `--no-network` | `--no-network` | Whether tasks can reach the network |
| `--jobs`, `-j` | `1` | Tasks to run concurrently |
| `--task`, `-t` | all | Run only these task ids. Repeatable. |
| `--category`, `-c` | all | Run only these categories. Repeatable. |
| `--prices` | — | JSON price table. Without one, cost is reported as unknown rather than zero. |
| `--out` | — | Directory to write `results-<date>-<model>.md` and `.json` into |

**Exit code is 0 whether or not tasks pass.** A failing task is a result, not a broken run. The
exit code is 1 only when the *harness* failed — the container would not start, a fixture is
unreadable — because a suite that never really executed must not look like a clean sweep.

!!! warning "`--sandbox local` is not an isolation boundary"

    It runs each task's commands as subprocesses on your machine, in a temporary copy of the
    fixture. It exists so tasks can be written and debugged without Docker in the way. Anything
    published from a local run should say that it was a local run.

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

Run the whole eval suite, four tasks at a time, and commit the report:

```bash
endstate eval --suite tasks/ --model gpt-4o-mini --jobs 4 --prices ./prices.json --out benchmarks/
```

Run one category against a self-hosted model:

```bash
endstate eval --suite tasks/ --category refactor --base-url http://localhost:8000/v1 --model Qwen/Qwen2.5-Coder-7B-Instruct
```

Debug a single task without Docker:

```bash
endstate eval --suite tasks/ --task fix-slugify --sandbox local
```
