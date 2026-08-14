# endstate — engineering plan

**Version:** 1.0 · **Owner:** Álvaro Diez de Pablos · **Window:** 5 weeks × ~6 h/week (30 h)
**Budget:** ≤ €150, expected ≤ €30 against the GCP $300 trial credit.

---

## 1. Objective

Ship a public, installable agent harness whose evaluation suite grades the **end state of a sandbox**
rather than the model's text output, and publish a reproducible benchmark comparing hosted and
self-hosted models on the same tasks.

### 1.1 Success criteria

The project is successful if **all six** are true at the end of Week 5. Every one is objectively
checkable — no criterion depends on anyone's opinion.

| ID | Criterion | Measurement |
|----|-----------|-------------|
| S1 | Installable from PyPI | `pip install endstate && endstate version` exits 0 on a clean machine |
| S2 | Eval suite runs end to end | `endstate eval --suite tasks/` returns a report for ≥ 20 tasks |
| S3 | Benchmark published | `benchmarks/` contains a committed report with ≥ 3 providers × ≥ 20 tasks |
| S4 | Self-hosted path proven | ≥ 1 provider in the benchmark is vLLM on GKE, provisioned by `terraform apply` |
| S5 | Quality gates hold | CI green on 3 Python versions: ruff, `mypy --strict`, coverage ≥ 85 % |
| S6 | Legible in 30 seconds | README leads with thesis + results table; a reader can state what is unusual about it |

### 1.2 Explicit non-goals

Web UI · TUI beyond `rich` · RAG or vector stores · multi-agent orchestration · IDE plugin ·
general-purpose framework · beating anyone on a public leaderboard.

Anything not serving §1 gets cut without discussion.

---

## 2. Milestones

Each milestone has a **Definition of Done** (binary), **acceptance tests** (executable), and
**metrics** (recorded). A milestone is not done until its acceptance command exits 0.

### M0 — Foundation ✅ *complete*

| | |
|---|---|
| **Deliverable** | Package skeleton, core types, telemetry, permissions, context, tools, sessions, loop, CLI, CI |
| **DoD** | `make check` passes; package builds; v0.0.1 on PyPI |
| **Acceptance** | `uv run ruff check . && uv run mypy && uv run pytest` |
| **Metrics achieved** | 59 tests · 96 % coverage · mypy strict clean · 0 lint errors |

**Shipped in M0**

- `types.py` — provider-agnostic `Message` / `ToolCall` / `Usage` / `Response`
- `telemetry/cost.py` — usage accounting; unknown prices **raise** rather than report zero
- `telemetry/trace.py` — in-process spans for provider calls, tool runs, denials
- `agent/permissions.py` — ordered rules, default-deny, destructive/exfiltration deny-list
- `agent/context.py` — `TokenBudget`, `DropOldest`, `SummariseMiddle`, recorded `CompactionEvent`
- `agent/tools/` — read, write, edit, glob, grep, bash, all path-confined to the workdir
- `agent/session.py` — SQLite sessions, checkpoint on **every** append
- `agent/loop.py` — the harness
- `providers/` — `Provider` Protocol, `FakeProvider`, Anthropic, OpenAI-compatible

---

### M1 — Harness hardening ✅ *core complete*

| | |
|---|---|
| **Deliverable** | Resume semantics that finish an interrupted run, `tree_hash()`, kill-point test suite |
| **DoD** | A killed run resumes and reaches the same end state as an uninterrupted run |
| **Acceptance** | `pytest tests/test_recovery.py` — kill at call *k*, resume, assert identical tree hash |
| **Metrics achieved** | 96 tests · 96 % coverage · resume fidelity 100 % at every kill point, both crash variants |

**Shipped in M1**

- `tree.py` — deterministic tree hashing; content not metadata, executable bit included, symlinks
  recorded rather than followed
- `RunResult.tree_hash()` — the assertion primitive for end-state grading
- Per-call result persistence (D8 at call granularity, not batch granularity)
- `AgentLoop.resume()` — reconciles outstanding tool calls, then continues without a new instruction
- `endstate run --resume <id>` with no prompt finishes an interrupted run; with a prompt it settles
  first, then continues the conversation
- `tests/test_recovery.py` — every kill point × {before, after} the side effect, plus a real
  `SIGKILL` test for the SQLite durability claim itself

**Mutation check** (each guard removed, suite must notice):

| Guard removed | Tests failing |
|---|---|
| Resume reconciliation | 11 of 20 |
| Per-call persistence | 1 of 20 |

The second row is the finding: with idempotent tools, batch-only persistence is invisible in the end
state, because losing the record of a completed call just means resume re-runs it to the same place.
It is only observable in the recorded history — or with a non-idempotent tool.

**Deferred** (cut order items 5 and adjacent, neither blocking): streaming CLI output, demo GIF.

**Known limit:** a crash *inside* a tool call, after the side effect and before any record of it, is
irreducible without transactional side effects. Resolved in part by `Tool.idempotent` in M2 — see
below — which stops resume replaying a call it cannot prove did not happen. Full correctness needs
idempotency keys, which this harness does not have.

---

### M2 — Eval runner and the first 12 tasks ✅ *complete*

| | |
|---|---|
| **Deliverable** | Docker sandbox, task spec, runner, graders, markdown report; 12 tasks (fix / feature / refactor) |
| **DoD** | `endstate eval --suite tasks/` produces a report; suite is deterministic |
| **Acceptance** | Same suite run twice on the same model+seed yields identical pass/fail vector |
| **Metrics achieved** | 256 tests · 98 % coverage · mypy strict clean · every task's graders proved load-bearing |

**Grader contract:** pure function of the sandbox's end state. No access to the transcript. This is
enforced by the signature — `grade(sandbox: Sandbox) -> Verdict` receives no messages — and the
enforcement is real: `resolve()` inspects the signature and refuses a grader whose first parameter
is not a positional `sandbox`, or that takes `messages`, `transcript`, `result` or `history`.

**Shipped in M2**

- `agent/tools/base.py` — `Tool.idempotent`, and `AgentLoop._settle` reading it. An outstanding call
  to a non-idempotent tool is answered "outcome unknown", not replayed. `BashTool.idempotent = False`
- `evals/sandbox.py` — `DockerSandbox` (one container per task, held open with `docker exec`,
  `--network none`, `--cap-drop ALL`, capped memory and pids) and `LocalSandbox` for development.
  `.git`/`.hg`/`.svn` pruned from every fixture; `seal()` freezes the end state before grading stages
  anything in
- `evals/task.py` — a task is a directory: `task.json`, `prompt.md`, `fixture/`, `holdout/`,
  `solution/`. `graders` is a list and the list is a conjunction
- `evals/graders.py` — `command_succeeds`, `files_unchanged`, `no_new_skips`, `changed_paths_within`,
  `paths_exist`/`paths_absent`, `file_matches`, `file_contains`, `pattern_count`
- `evals/runner.py` — per-task sandbox, provider and accountant; deadline that ends the run instead of
  raising, so a timed-out task is still graded; `--jobs` without losing task order
- `evals/report.py` — markdown plus JSON; unpriced models render `—`, never `0.00`
- `endstate eval --suite tasks/` with `--sandbox`, `--task`, `--category`, `--jobs`, `--out`
- 5 bug-fix, 4 multi-file feature, 3 refactor tasks, each with held-out tests and a reference solution

**Verified against a real daemon** (Docker Desktop 29.7.2, `python:3.12-slim`): all 12 tasks run
in containers, network egress blocked (`socket.create_connection` to 1.1.1.1 fails), bind mount live
in both directions, no container outlives its task. Two integration tests assert this and skip when
no daemon is reachable, so CI — which has one — runs them. Suite wall clock: **1.7 s at `--jobs 4`**,
and the pass/fail vector was identical across two consecutive runs.

**Task-level mutation check** (`tests/test_suite.py`, 12 tasks × both directions):

| Assertion | Result |
|---|---|
| Graders **fail** on the untouched fixture | 12 of 12 |
| Graders **pass** on the reference solution | 12 of 12 |

This is the M2 analogue of M3's guard sabotage and it earned its keep while the suite was being
written: several graders passed on the unsolved fixture on the first attempt, and two rejected their
own reference solution. Neither is visible by reading the task definition.

**Deviations from the plan as written**

- `Task.grader: str` became `Task.graders: list[GraderSpec]`. Every interesting task is a
  conjunction — *did the work* **and** *did not cheat* — and a list makes that the only available
  shape instead of something each task author has to remember.
- 12 tasks, not 10. The 5 + 4 + 3 breakdown below always summed to 12; the heading was wrong.

**Deferred:** repo public, v0.1.0 tag, first post — the shipping steps, not the engineering.

---

### M3 — The differentiating tasks ✅ *complete*

| | |
|---|---|
| **Deliverable** | 10 further tasks: compaction, permissioning, checkpoint recovery, cost |
| **DoD** | Each category has a task that **fails** against a deliberately broken harness build |
| **Acceptance** | Mutation check: disable compaction → compaction tasks fail; disable policy → permissioning fail |
| **Metrics achieved** | 344 tests · 98 % coverage · mutation sensitivity 100 % · 22 tasks total |

| Category | Count | Grader asserts |
|---|---|---|
| Long-horizon / compaction | 3 | Task completes **and** `compaction_events ≥ 1` **and** end state correct |
| Permissioning | 3 | Destructive request **refused**; tree hash unchanged; `denied_calls ≥ 1` |
| Checkpoint recovery | 2 | Killed at tool call *k*, resumed by a fresh loop, work still lands |
| Cost regression | 2 | Task completes under a declared step or token budget |

**Mutation check** (`tests/test_mutation.py`) — each guard removed, the category must notice:

| Guard removed | Result |
|---|---|
| The permission policy | `deny-recursive-delete` fails: `rm -rf data` runs, tree changes |
| The context budget | `compaction-audit-every-module` fails: end state correct, `compaction_events == 0` |
| Resume reconciliation | killed run leaves the suite red; the resumed one does not |

The compaction row is the interesting one. With the budget removed the agent does the same work and
leaves an identical, *correct* end state — the task fails only because compaction never fired. A
suite graded on files alone would pass it and report coverage it does not have.

**Run-level assertions without widening the grader contract**

`compaction_events ≥ 1` is not a property of the filesystem, so no grader can see it without being
handed something other than the sandbox. Rather than add a parameter, the task manifest carries a
`requires` block that the **runner** evaluates and conjoins with the grader's verdict:

```json
"requires": { "denied_calls": { "min": 1 } }
```

`grade(sandbox) -> Verdict` is untouched. What keeps that from being a loophole is the shape of
`RunRequirements`: a closed set of typed counters the harness recorded itself, with
`extra="forbid"`, so a manifest naming `final_text` is rejected at load time rather than silently
ignored.

**Findings while building it**

- **A bound typo asserted nothing.** `{"minimum": 1}` parsed as a bound with no ends, which passes
  for any value — the requirement read as asserted in the task file and checked nothing. Now an
  error. This is the exact failure mode the mutation check exists to catch, found in the mechanism
  built to do the catching.
- **A grader that raised was scored as a pass.** Merging two verdicts recomputed `passed` from the
  combined checks, and a grader that threw reports a reason with *no* checks — so the merge read the
  empty list as "nothing failed".
- **An oracle that writes perfect files passes 16 of 22.** It fails every compaction and
  permissioning task, because writing the right bytes is not what those categories test.

**Deviation from the plan as written:** recovery tasks assert that the task's own graders pass after
a kill and resume, rather than comparing tree hashes against a second uninterrupted run. Two runs of
a real model differ for reasons that have nothing to do with recovery, so hash equality is only
meaningful with a scripted provider — where it already lives, in `tests/test_recovery.py`.

---

### M4 — Self-hosted serving and the benchmark · Week 4 · 3 h

| | |
|---|---|
| **Deliverable** | Terraform GKE + spot L4 node pool, vLLM deployment, full benchmark across 3 providers |
| **DoD** | `benchmarks/results-<date>.md` committed with real numbers; infrastructure destroyed |
| **Acceptance** | `terraform apply` → `make bench` → `make gpu-down` → `terraform show` reports no GPU nodes |
| **Metrics** | GPU-hours consumed · total USD spent · €/task per provider |

**Cost controls — non-negotiable, set before the first `terraform apply`**

1. Dedicated GCP project, deletable wholesale
2. Budget alerts at €25 and €50
3. `min_node_count = 0` on the GPU pool
4. `make gpu-down` exists and is tested **before** `make gpu-up` is written
5. Same-day teardown; calendar reminder on any GPU day

**Benchmark output columns:** provider · model · pass rate · median steps · input/output tokens ·
USD per task · p95 latency · compaction events per task.

---

### M5 — Make it legible · Week 5 · 6 h

| | |
|---|---|
| **Deliverable** | README rewrite, mkdocs site, v1.0.0, blog post, Show HN |
| **DoD** | Criterion S6 met, verified by a reader who has not seen the project |
| **Acceptance** | Two people can state the thesis after 30 s of reading; both correct |
| **Metrics** | Post impressions · unique repo visitors · inbound messages |

---

## 3. Quality gates

Enforced in CI on every push. A red gate blocks merge; none are advisory.

| Gate | Threshold | Tool |
|---|---|---|
| Lint | 0 errors | `ruff check` |
| Format | no diff | `ruff format --check` |
| Types | 0 errors, strict | `mypy` |
| Unit tests | 100 % pass | `pytest` |
| Coverage | ≥ 85 % | `pytest-cov` (network adapters and CLI excluded — see `pyproject.toml`) |
| Python support | 3.10, 3.11, 3.12, 3.13, 3.14 | CI matrix |
| Supply chain | no tokens in repo | PyPI Trusted Publishing (OIDC) |

**Current status:** all green. 344 tests, 98 % coverage, mypy strict clean.

`tasks/` is excluded from ruff. The fixtures contain deliberate bugs — a mutable default argument, an
off-by-one — that are the thing being graded, and a linter that fixes them deletes the task.

---

## 4. Test strategy

Four layers, each answering a different question.

| Layer | Question | Where | Network |
|---|---|---|---|
| Unit | Does this function do what it claims? | `tests/test_*.py` | none |
| Contract | Does every provider adapter satisfy the Protocol? | `tests/test_provider_contract.py` (M4) | recorded fixtures |
| Integration | Does the loop behave end to end? | `FakeProvider` + real filesystem | none |
| Eval | Does the *agent* accomplish the task? | `tasks/` in Docker | real models |

The distinction that matters: **unit tests grade the harness; evals grade the agent.** Conflating them
is how projects end up with a test suite that passes while the product is broken.

**Already covered (M0):** path escape attempts · deny-list bypasses (18 parametrised commands) ·
ambiguous edits · shell timeouts · output truncation · budget arithmetic · compaction pinning and
recording · session durability across process boundaries · denied calls leaving the sandbox untouched ·
max-steps enforcement · unknown-model pricing raising rather than under-reporting.

---

## 5. Risk register

| ID | Risk | Likelihood | Impact | Mitigation | Trigger to act |
|----|------|-----------|--------|-----------|----------------|
| R1 | Forgotten GPU node pool | Medium | High (€500+) | Budget alerts, `min_nodes=0`, `gpu-down` first | Any alert fires |
| R2 | Eval suite is flaky, results not credible | Medium | High | Determinism test in M2 DoD; pinned model versions; fixed seeds | Flake rate > 5 % |
| R3 | Scope creep into a framework | High | High | §1.2 non-goals; cut order in §6 | Any non-goal appears in a branch |
| R4 | Frontier API costs overrun | Low | Medium | Develop against cheap models; full runs only for published results | Spend > €80 |
| R5 | Self-hosted model too weak to pass any task | Medium | Medium | **This is a finding, not a failure** — publish it | — |
| R6 | 5 weeks slips | Medium | Low | Cut order in §6; M2 is the minimum shippable point | Week 4 with no eval runner |
| R7 | Name taken on PyPI during build | Low | Medium | Claim v0.0.1 in Week 1 | — |

R5 is worth restating: "a 14 B model self-hosted on one L4 passes 6/20 tasks at 1/40th the cost" is a
*more* interesting result than parity, and it is the one you can actually defend in an interview.

---

## 6. Cut order

Under time pressure, cut strictly in this order:

1. mkdocs site (README suffices)
2. Refactor task category (3 tasks)
3. `SummariseMiddle` strategy (`DropOldest` alone still demonstrates budgeting)
4. Third provider (two still make a comparison)
5. Streaming output

**Never cut:** the Docker sandbox · end-state graders · compaction / permissioning / recovery
categories · the published cost table. Those four *are* the project.

---

## 7. Decision log

Recorded so the reasoning survives, and so interview answers are consistent with the repo.

| # | Decision | Rationale | Alternative rejected |
|---|---|---|---|
| D1 | Build the loop from primitives | The harness *is* the artifact; a framework hides the interesting decisions | LangGraph — would demote this to "a LangGraph demo" |
| D2 | Deterministic graders, no LLM judge in the primary path | Credibility and reproducibility; a judge is another model to debug | LLM-as-judge |
| D3 | SQLite for sessions | Zero infrastructure to run locally; checkpointing is a durability problem, not a scale problem | Postgres, Redis |
| D4 | Prices as user-supplied data; unknown price raises | A wrong cost number is worse than a missing one | Hardcoded price table |
| D5 | Default-deny permission policy | Failure modes are asymmetric: a wrongly denied command is an annoyance, a wrongly allowed one is an incident | Default-allow with a deny-list |
| D6 | Heuristic token counter by default | Must work against providers whose tokeniser is not public | Per-provider tokenisers as a hard dependency |
| D7 | One disposable container per eval task | Determinism, parallelism, and the only reason it is sane to give an agent a shell | Shared sandbox, subprocess isolation |
| D8 | Checkpoint *after* the tool result | Re-applying an already-applied side effect on resume is the classic bug | Checkpoint before the step |

---

## 8. Tracked metrics

Recorded per benchmark run and committed alongside results, so trends are visible over time.

**Harness:** tests · coverage % · mypy errors · public API surface
**Agent:** pass rate by category · median steps · compaction events/task · denied calls/task ·
resume fidelity
**Economics:** input/output tokens per task · USD per task per provider · GPU-hours · total spend
**Reach:** repo visitors · PyPI downloads · post impressions · inbound messages

Reach metrics are recorded but explicitly **not** success criteria. Stars are not the point; the
benchmark table and the interview answers are.

---

## 9. Immediate next actions

| # | Action | Owner | When |
|---|--------|-------|------|
| 1 | Publish v0.0.1 to PyPI (claim the name) | Álvaro | This week |
| 2 | Create GitHub repo, push, keep **private** until M2 | Álvaro | This week |
| 3 | Create dedicated GCP project + €25 budget alert | Álvaro | Before any Terraform |
| 4 | Configure PyPI Trusted Publishing for the repo | Álvaro | Before v0.1.0 |
| 5 | Begin M1 | Álvaro | Week 1 |
