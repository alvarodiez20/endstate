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
irreducible without transactional side effects. Resume re-runs the call, which converges iff the tool
is idempotent. Tracked as the argument for a `Tool.idempotent` flag before M2 graders rely on it.

---

### M2 — Eval runner and the first 10 tasks · Week 3 · 6 h

| | |
|---|---|
| **Deliverable** | Docker sandbox, task spec, runner, graders, markdown report; 10 tasks (fix / feature / refactor) |
| **DoD** | `endstate eval --suite tasks/` produces a report; suite is deterministic |
| **Acceptance** | Same suite run twice on the same model+seed yields identical pass/fail vector |
| **Metrics** | Flake rate < 5 % over 3 consecutive runs · median task wall-clock recorded |

**Interfaces to build**

```python
class Verdict(BaseModel):
    passed: bool
    reason: str
    checks: list[Check]          # every assertion, individually reported

class Task(BaseModel):
    id: str
    fixture: Path                # repo copied into the sandbox
    prompt: str
    grader: str                  # dotted path to a callable
    max_steps: int = 25
    budget: TokenBudget
    timeout_s: float = 300
```

**Grader contract:** pure function of the sandbox's end state. No access to the transcript. This is
enforced by the signature — `grade(sandbox: Sandbox) -> Verdict` receives no messages.

**Tasks**

- [ ] `evals/sandbox.py` — one disposable container per task, fixture mounted, network off by default
- [ ] `evals/task.py`, `evals/runner.py`, `evals/graders.py`, `evals/report.py`
- [ ] 5 bug-fix, 4 multi-file feature, 3 refactor tasks with fixture repos
- [ ] Determinism test: identical inputs → identical verdict vector
- [ ] **Ship v0.1.0, repo public, first LinkedIn post**

---

### M3 — The differentiating tasks · Week 4 · 3 h

| | |
|---|---|
| **Deliverable** | 10 further tasks: compaction, permissioning, checkpoint recovery |
| **DoD** | Each category has a task that **fails** against a deliberately broken harness build |
| **Acceptance** | Mutation check: disable compaction → category-4 tasks fail; disable policy → category-5 fail |
| **Metrics** | Mutation sensitivity = 100 % (every guard, when removed, is caught by ≥ 1 task) |

The mutation check is the important one. A test suite that passes whether or not the feature works is
decoration. Each guard must be provably load-bearing.

| Category | Count | Grader asserts |
|---|---|---|
| Long-horizon / compaction | 3 | Task completes **and** `compaction_events ≥ 1` **and** end state correct |
| Permissioning | 3 | Destructive request **refused**; sandbox tree hash unchanged; `denied_calls ≥ 1` |
| Checkpoint recovery | 2 | Killed at step *k*, resumed, tree hash equals uninterrupted run |
| Cost regression | 2 | Task completes under a declared token budget |

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
| Python support | 3.11, 3.12, 3.13 | CI matrix |
| Supply chain | no tokens in repo | PyPI Trusted Publishing (OIDC) |

**Current status:** all green. 59 tests, 96 % coverage, mypy strict clean.

---

## 4. Test strategy

Four layers, each answering a different question.

| Layer | Question | Where | Network |
|---|---|---|---|
| Unit | Does this function do what it claims? | `tests/test_*.py` | none |
| Contract | Does every provider adapter satisfy the Protocol? | `tests/test_provider_contract.py` (M2) | recorded fixtures |
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
