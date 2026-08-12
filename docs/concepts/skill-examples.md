# Skill examples

[Skills](skills.md) explains the mechanism: a folder, two required frontmatter fields, three levels
of progressive disclosure. This page is the concrete half — what already exists that you can install
today, three worked `SKILL.md` files written against this repository's real conventions, and a
recommended starting set if you are building a coding agent of your own.

!!! info "Status"

    `endstate` has no skill loader, so nothing on this page is a feature of this project. The three
    worked examples are written for *your* agent working on *this* codebase — every rule in them is
    checkable against
    [`pyproject.toml`](https://github.com/alvarodiez20/endstate/blob/main/pyproject.toml),
    the [`Makefile`](https://github.com/alvarodiez20/endstate/blob/main/Makefile) and
    [`CONTRIBUTING.md`](https://github.com/alvarodiez20/endstate/blob/main/CONTRIBUTING.md), which is
    the point: a good conventions skill contains no advice you cannot verify.

## Part one: what already exists

### For a senior software engineer

Anthropic's [`engineering` plugin](https://github.com/anthropics/knowledge-work-plugins/tree/main/engineering)
in the open-source knowledge-work-plugins repository is the most useful first-party set. It bundles
ten skills that map onto the parts of the job that are not writing code:

| Skill | What it covers |
| --- | --- |
| `architecture` | Writing and evaluating architecture decision records — trade-offs, consequences |
| `system-design` | API design, data modelling, service boundaries |
| `code-review` | Security, performance, correctness on a diff or PR |
| `testing-strategy` | Test plans, coverage, what to test at which level |
| `debug` | Reproduce, isolate, diagnose, fix — as a procedure rather than a vibe |
| `tech-debt` | Identifying, categorising and prioritising refactoring work |
| `documentation` | READMEs, runbooks, API docs, onboarding guides |
| `incident-response` | Triage, comms, blameless postmortem |
| `deploy-checklist` | Pre-deploy verification, migrations, rollback triggers |
| `standup` | Turning commits, PRs and ticket moves into a shareable update |

The interesting thing about that list is how little of it is about *writing* code. It is the
procedural knowledge a senior engineer carries and a junior one does not, which is exactly the gap
[skills exist to close](skills.md).

[Superpowers](https://github.com/obra/superpowers) is the notable community alternative and takes a
different shape: rather than ten independent skills it chains a methodology — brainstorming, then
planning, then test-driven implementation, then a review pass — with each phase a skill that hands
off to the next. Worth reading even if you do not install it, because composition is the part most
skill collections get wrong.

### For a senior Python engineer

This is the gap, and it is worth being honest about it. There is no canonical first-party Python
conventions skill, and the community ones are mostly generic — "use type hints, use `ruff`, use
`pytest`" — which a competent model already knows and which therefore buys you nothing but tokens.

Language-and-repo conventions are the category you almost always write yourself, because the value
is entirely in the specifics: *this* line length, *this* mypy strictness, *this* coverage gate,
*this* reason we use `Decimal`. That is why the second worked example below is a Python one.

The general-purpose Python material that *is* worth installing is tooling-shaped rather than
style-shaped — skills that know how to drive `uv`, diagnose a broken virtualenv, or read a `mypy`
error cascade back to its root cause.

### For a code reviewer

Two things worth knowing here, in increasing order of specificity:

- **[`engineering/code-review`](https://github.com/anthropics/knowledge-work-plugins/tree/main/engineering)**
  — the general reviewer above. Structured around security, performance, correctness and
  maintainability. A reasonable default and deliberately generic.
- **[Trail of Bits' skills](https://github.com/trailofbits/skills)** — a security-research firm's
  audit workflows, released openly under CC BY-SA 4.0. Differential review of a diff, building
  architectural context before reviewing, static analysis with CodeQL and Semgrep, writing Semgrep
  rules, variant analysis to find the same bug elsewhere in a codebase, and verifying that a fix
  commit actually fixes the finding without introducing a new one.

That last set is the most instructive collection of skills in public, for a reason worth naming: the
skills encode a *procedure with a decision tree*, not a checklist of things to look for. "Check for
SQL injection" is something the model already does. "Here is how to establish whether this diff
changes a trust boundary, and what to read first if it does" is not.

!!! warning "Everything in this section is third-party code your agent will obey"

    Install counts and star counts are popularity, not review. A skill is instructions and scripts
    that run inside your sandbox, and a malicious one needs no exploit — it just needs the model to
    do what the file says. Read the `SKILL.md`, read anything in `scripts/`, and look specifically
    for instructions that fetch from the network. See
    [the security section of the skills page](skills.md#the-security-problem-stated-plainly).

## Part two: three worked examples

Written for this repository. Read them for the shape rather than the content — each one demonstrates
a different thing a skill can do.

### 1. `endstate-python` — conventions

The point of a conventions skill is to replace *"follow the project style"* with something a model
cannot get subtly wrong. Every line here corresponds to a configured gate.

```markdown
---
name: endstate-python
description: Python conventions, tooling and quality gates for the endstate repository.
  Use when writing, modifying or reviewing Python in this repo, or when a CI gate
  (ruff, mypy, pytest, coverage) has failed and you need to know what it wants.
compatibility: Requires uv and the repo's dev group installed (`make install`).
---

# Python in endstate

## Run the gates before claiming you are done

`make check` runs exactly what CI runs. Do not report a change as complete until it exits 0.

| Command | Gate |
| --- | --- |
| `uv run ruff check .` | Lint: rulesets E, F, I, UP, B, SIM |
| `uv run ruff format --check .` | Formatting, line length 100 |
| `uv run mypy` | Strict, over `src/endstate`, target 3.10 |
| `uv run pytest` | `-q --strict-markers`, coverage gate at 85% |

CI runs these on 3.11, 3.12 and 3.13. `target-version` is `py310`, so do not use syntax
newer than 3.10 even though the test matrix is newer.

## Use uv, never pip

Dependencies are managed with uv and locked in `uv.lock`. `pip install` inside this repo
produces an environment that does not match CI.

## Repo-specific rules that are not style preferences

- **`Decimal`, never `float`, for money.** Prices parse from JSON *strings* so they never
  touch a float on the way in. See `telemetry/cost.py`.
- **`Protocol`, not ABC, at provider seams.** Adapters must not import from the harness;
  structural typing keeps the dependency arrow pointing one way.
- **No network in unit tests.** Drive the loop with `FakeProvider`. If a test needs a real
  provider it belongs in the integration runs, not the suite that gates a merge.
- **Markdown is excluded from ruff on purpose.** Do not "fix" fenced Python in `.md` files;
  `extend-exclude` is there because illustrative snippets are not source.
- **Provider adapters and the CLI are omitted from coverage** deliberately, so the gate
  measures logic that is testable offline. Do not add tests purely to raise the number.

## Commits

Conventional Commits — releases are automated from them. `docs:` and `chore:` do not bump
the version; `feat:` bumps the minor and `fix:` the patch.
```

Three things to notice:

- **The description says when, not only what** — including the failure case ("a CI gate has
  failed"), which is when a model is most likely to need it and least likely to think of it.
- **Every rule is falsifiable.** A reviewer can check each line against `pyproject.toml`. Skills rot
  silently, and the only defence is writing claims that can be caught when they go stale.
- **It explains the non-obvious ones.** "No `float` for money" without the reason gets followed;
  with the reason it also gets applied to the case you did not enumerate.

### 2. `endstate-review` — a reviewer with progressive disclosure

The reviewer is where level 3 earns its keep. The main file stays short; the deep material lives in
`references/` and is read only when the diff touches something that needs it.

```
endstate-review/
├── SKILL.md
└── references/
    ├── harness-invariants.md   # the D-numbered decisions and how to spot a violation
    └── security.md             # deny-list ordering, exfiltration patterns, path confinement
```

```markdown
---
name: endstate-review
description: Review a change to the endstate harness for correctness, security and
  harness-invariant violations. Use when reviewing a diff, a PR or staged changes in
  this repository, or when asked whether a change is safe to merge.
allowed-tools: Bash(git diff:*) Bash(git log:*) Bash(make check) Read Grep
---

# Reviewing endstate

## Order of work

1. `git diff` the change. Read it fully before forming a view.
2. Classify what it touches. Anything under `agent/permissions.py`, `agent/tools/`,
   or `agent/session.py` is invariant-bearing — read
   `references/harness-invariants.md` before continuing.
3. Anything touching the deny-list, path confinement or `bash` — also read
   `references/security.md`.
4. Run `make check`. A review that has not run the gates is an opinion.
5. Report findings as: must-fix, should-fix, nit. Say which is which.

## The four things that are usually wrong

- **Permission rule ordering.** Rules are first-match-wins with denies at the top.
  A new `ALLOW` inserted above a deny silently disables it, and the test suite still
  passes. Check the position of every added rule, not only its content.
- **Checkpoint before the side effect.** Outcomes are persisted, never intentions.
  A change that records a tool call before running it reintroduces the ambiguity
  D8 exists to remove.
- **Silent cost regressions.** A new field on a message, a longer tool description,
  or an extra system-prompt line is paid on every step of every run. Say so in review.
- **Tests that assert on the transcript.** The project grades end states. A test that
  passes because the agent *said* it did the thing is the failure mode this repo exists
  to argue against.

## What not to comment on

Formatting and import order are `ruff`'s job and it already ran. Reviewing them by hand
spends your credibility on the cheapest possible finding.
```

The `allowed-tools` line is doing real work: the skill needs to read a diff and run the gates, and
nothing else. Narrowing it is not enforcement — a
[policy is the only thing that enforces](permissions.md) — but it does document intent, and a
reviewer skill that requests `Bash(*)` deserves a second look.

### 3. `endstate-change-plan` — process, not knowledge

The most valuable skill for a mature codebase is often the one that stops work rather than guiding
it.

```markdown
---
name: endstate-change-plan
description: Plan a change to endstate before writing code. Use at the start of any task
  that adds a feature, changes an interface, or touches more than one module — and any
  time a request sounds like it might be a project non-goal.
---

# Before writing code in endstate

## Check it is not a non-goal first

`docs/design/non-goals.md` lists what this project will not do: web UI, RAG or vector
stores, multi-agent orchestration, MCP client, general-purpose framework, leaderboard
chasing. If the request matches one, say so and stop. Do not implement it and mention
the conflict afterwards.

## Then check the decision log

`docs/design/decisions.md` holds D1–D8. If the change contradicts one, the change is not
the deliverable — amending the decision is, and that is a conversation to have first.

## Then state the plan in four lines

1. Which milestone in `PLAN.md` this serves. If none, say so.
2. The smallest change that would work.
3. What test would fail today and pass afterwards.
4. What could be removed to make the guard prove itself — the mutation check.

Only then write code.

## The default is smaller

This project's stated highest risk is scope creep into a framework, arriving as a
reasonable feature request that would only take an afternoon. When in doubt, propose the
version with fewer options and no new configuration surface.
```

No technical content at all. It is entirely about routing a request to the right decision, which is
the sort of thing that lives in a senior engineer's head and nowhere in a codebase.

## Part three: what to bundle in a coding agent

If you are building an agent rather than configuring one, the question changes from "which skills
should I install" to "what belongs in the box."

### The budget, so it stops being abstract

Level 1 is roughly 100 tokens per skill, always loaded. Thirty bundled skills cost ~3,000 tokens of
permanent context — real, but small next to a single file read.

**The token cost is not the binding constraint. Description collision is.** Two skills whose
descriptions overlap produce the same failure as two tools that both expose a `search`: the model
picks a plausible wrong one and proceeds confidently. The
[MCP page](mcp-and-tool-discovery.md) makes this argument about tools and it applies unchanged here.
Practically: you can afford far more skills than you can afford *ambiguous* skills.

### A starting set

Six categories, roughly in order of how much they pay back:

| Category | Examples | Why it belongs in the box |
| --- | --- | --- |
| **Verification** | How to run this project's tests, lint, typecheck; what a green build means | The single highest-value skill in a coding agent. Without it the agent stops at "looks right" |
| **Repo conventions** | Per-language and per-repo style, tooling, structure | Always custom, always the most-fired skill you will ship |
| **Process** | Plan before code, TDD, systematic debugging, review before done | Changes *when* the agent does things, which is where most bad output comes from |
| **Output formats** | Commit messages, PR descriptions, changelogs, ADRs | Cheap, deterministic-ish, and immediately visible to humans |
| **Recovery** | Broken virtualenv, dependency conflict, failing migration, flaky test triage | Fires rarely, saves a whole run when it does |
| **Domain and ops** | Incident response, deploy checklist, on-call runbooks | Only if your agent touches production. Otherwise dead weight |

Two that are widely shipped and worth thinking twice about: a **skill-authoring** skill, so the agent
can capture its own successful approaches — powerful, and it means your agent writes instructions it
will later obey, which is a loop worth watching. And **subagent delegation**, which is a real
technique and carries the costs on the [subagents page](subagents.md).

### What should not be a skill

The most useful part of this page, if you are designing the box:

| If it is… | It belongs in… | Because |
| --- | --- | --- |
| Needed on every single task | The system prompt | A skill that always fires is progressive disclosure with extra steps |
| Deterministic | A script or a tool | Predicting the output of `sorted()` is strictly worse than calling it |
| Really data — a schema, a price table, an API reference | A file the agent reads, referenced *from* a skill | Level 3 exists for exactly this |
| A rule that must hold | The [permission policy](permissions.md) | **A skill is advice. The model can ignore it, and an injected instruction can talk it out of anything.** |

The last row is the one to internalise. It is tempting to write a skill that says "never force-push"
and consider force-pushing handled. It is not handled: it is *suggested*. Anything whose violation
would be an incident belongs in a deny-list that runs before the tool does, not in a markdown file
the model reads and weighs against everything else in its context.

### Build them from failures, not from a taxonomy

Anthropic's own guidance is to start with evaluation — run the agent on representative tasks, watch
where it struggles, and write skills against the observed gaps. The list in the table above is a
prompt for that exercise, not a shopping list.

There is a version of this that fits the rest of these docs particularly well. If you can write an
eval task that the agent **fails without the skill and passes with it**, the skill is load-bearing
and you can prove it. If you cannot, you have written documentation that costs tokens on every run.

That is [the mutation check](evaluation.md#the-mutation-check) pointed at your skill library, and it
is the only way to find out which half of it is inert.

## What to check in your own bundle

- For each skill: what would break if you deleted it? If you cannot answer, delete it.
- Could two of your descriptions match the same request? Which one wins, and did you decide that?
- Is your most-fired skill the one that tells the agent how to verify its own work?
- Is anything load-bearing for safety expressed as a skill rather than as a policy?
- For every third-party skill: have you read its `scripts/`?

## Sources

- [anthropics/knowledge-work-plugins](https://github.com/anthropics/knowledge-work-plugins) — the `engineering` plugin and ten role skills, Apache 2.0
- [anthropics/skills](https://github.com/anthropics/skills) — reference skills, the spec, and a skill template
- [trailofbits/skills](https://github.com/trailofbits/skills) — security research and audit workflows, CC BY-SA 4.0
- [obra/superpowers](https://github.com/obra/superpowers) — a composed development methodology as chained skills
- [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) — the authoring guidance, including "start with evaluation"
- [Agent Skills specification](https://agentskills.io/specification) — frontmatter fields and their constraints
