# Writing an eval task

A task is a directory. Everything about it is a file you can read, diff and argue with.

```text
tasks/fix-chunk-off-by-one/
├── task.json      metadata, budget, graders
├── prompt.md      what the agent is told
├── fixture/       copied into the sandbox; this is the agent's whole world
├── holdout/       staged in at grading time only — the agent never sees it
└── solution/      a reference fix, used to prove the graders are load-bearing
```

Run one while you are writing it:

```bash
endstate eval --suite tasks/ --task fix-chunk-off-by-one --sandbox local
```

## The manifest

```json
{
  "id": "fix-chunk-off-by-one",
  "category": "bug-fix",
  "description": "chunk() silently drops the final partial chunk.",
  "max_steps": 20,
  "timeout_s": 600.0,
  "budget": { "max_context_tokens": 60000, "reserve_output_tokens": 4000 },
  "graders": [
    {
      "name": "endstate.evals.graders:command_succeeds",
      "args": { "command": "python -m unittest discover -s tests -t . -q" }
    },
    {
      "name": "endstate.evals.graders:files_unchanged",
      "args": { "paths": ["tests/test_chunk.py"] }
    }
  ]
}
```

`graders` is a list and the list is a **conjunction**: every check from every grader must pass. That
is the shape the interesting task definitions have — *did the work* **and** *did not cheat to get
there* — and making it the only shape available means nobody has to remember to write the second
half as a separate step.

`prompt.md` wins over a `prompt` key in the manifest, because prose belongs in a file someone will
actually edit.

## The four assertions every task should make

A task graded only by "the test suite passes" has swapped a fluency exploit for a test-editing
exploit. The shipped tasks all make these four, and this repo's own test suite fails if a task tries
to get by on a command alone.

```json
[
  { "name": "endstate.evals.graders:command_succeeds",
    "args": { "command": "python -m unittest discover -s tests -t . -q" } },

  { "name": "endstate.evals.graders:files_unchanged",
    "args": { "paths": ["tests/test_chunk.py"] } },

  { "name": "endstate.evals.graders:no_new_skips" },

  { "name": "endstate.evals.graders:changed_paths_within",
    "args": { "allowed": ["chunker/*", "*.md"] } }
]
```

The fifth assertion is not a grader: it is the `holdout/` directory. Put tests there that the agent
never sees, and special-casing the visible inputs stops working.

## The grader contract

```python
def grade(sandbox: Sandbox) -> Verdict: ...
```

One argument, and it is the sandbox. A grader is resolved from its dotted path before it runs, and
resolution inspects the signature: the first parameter must be `sandbox` and positional, and
anything named `messages`, `transcript`, `result` or `history` is refused. See
[Evaluation](../concepts/evaluation.md#the-contract-is-enforced-by-the-signature) for why that is
enforced rather than documented.

Arguments beyond the sandbox come from `args` and are bound before the grader is called, so the
callable the runner holds really does take only the sandbox.

### Writing your own

Put it anywhere importable and point at it with `module:function`:

```python
# mytasks/graders.py
from endstate.evals import Check, Sandbox, Verdict


def no_secrets_committed(sandbox: Sandbox, *, pattern: str = r"sk-[A-Za-z0-9]{20,}") -> Verdict:
    import re

    offenders = [
        path for path, text in sandbox.end_state_files().items() if re.search(pattern, text)
    ]
    return Verdict.from_checks(
        [Check(name="no secrets in the tree", passed=not offenders, detail=", ".join(offenders))]
    )
```

```json
{ "name": "mytasks.graders:no_secrets_committed" }
```

Return every check you ran, not just the failing one. "The tests pass but you edited them" and "the
tests fail" are different findings, and a verdict that collapses to one boolean cannot say which.

## What the sandbox gives a grader

| Method | Answers |
| --- | --- |
| `run(command)` | Did it work? Returns exit code, stdout, stderr. |
| `read_text(path)` | What is in the file now? Missing reads as `""`. |
| `fixture_text(path)` | What was in it before the agent started? |
| `end_state_files()` | Every text file in the end state, keyed by relative path. |
| `changed_paths()` | What did the agent add, edit or delete? |
| `tree_hash()` | Is this sandbox byte-for-byte what it was? |
| `exists(path)` | Is it there? |

`fixture_text` is the one worth noticing. The pristine fixture is kept beside the live tree, so "is
this file byte-for-byte what we shipped?" is answerable — which is what catches an agent editing the
tests instead of the code.

Note that these read the **sealed** end state, frozen when the agent stopped and before the held-out
tests were staged in. A grader cannot accidentally assert on its own side effects.

## Fixtures

- **Standard library only.** The sandbox has no network, so a fixture that needs `pip install`
  cannot run. The shipped tasks use `unittest` rather than pytest for exactly this reason.
- **`tests/` needs an `__init__.py`** for `unittest discover -s tests -t .` to import it.
- **Ship the failing test.** For a bug-fix task the suite should be red on arrival: that is the
  signal the agent works from, and a task whose tests already pass is a task with no feedback loop.
- **No version control history.** `.git`, `.hg` and `.svn` are pruned when the fixture is copied in,
  so you do not have to remember — but do not build a fixture whose answer is only hidden by that.

## The solution directory

`solution/` is overlaid on the fixture to check that the graders discriminate. It is never given to
an agent, and the test that uses it asserts both directions:

- the graders **fail** on the untouched fixture, and
- the graders **pass** on the reference solution.

Write it. A grader that passes either way is measuring nothing, and it is much easier to write one
of those than most people expect — the failure is silent and looks exactly like a well-behaved
suite.

## Categories

`bug-fix`, `feature`, `refactor`, `compaction`, `permissioning`, `recovery`, `cost`. The first three
are shipped; the rest are the differentiating categories, planned for M3. Categories are validated
at load time, so a typo is an error rather than a task that quietly never runs in any filter.
