# CHANGELOG


## v0.2.0 (2026-08-14)

### Features

- Add the four differentiating task categories and the mutation check
  ([#12](https://github.com/alvarodiez20/endstate/pull/12),
  [`8bbbbbd`](https://github.com/alvarodiez20/endstate/commit/8bbbbbdd589590099518a122f0a5a37036da80ea))

Closes M3. Ten more tasks — compaction, permissioning, recovery, cost — bringing the suite to
  **22**, which also clears S2's "≥ 20 tasks".

These are the categories that break real deployments and that almost nothing tests. Each is a
  **conjunction**: the work *and* the guard.

## Asserting on the run without widening the grader contract

`compaction_events >= 1` is not a property of the filesystem. Neither is "the policy refused
  something" — an agent that ignored the request leaves exactly the same tree as one the harness
  stopped. The obvious fix is handing the grader the run result, which reopens the door the
  signature closed.

Instead the *task* declares what the run must have done, and the **runner** checks it:

```json "requires": { "denied_calls": { "min": 1 } } ```

`grade(sandbox) -> Verdict` is untouched. What stops this being a loophole by another name:
  `RunRequirements` is a closed set of typed counters the harness recorded itself — policy
  decisions, compaction events, token totals — with unknown keys **rejected at load time**. A
  manifest naming `final_text` is an error, not a silently ignored field.

## The mutation check

`tests/test_mutation.py`. Each guard removed on purpose; the category must notice.

| Guard removed | Result | | --- | --- | | The permission policy | `deny-recursive-delete` fails —
  `rm -rf data` runs, tree changes | | The context budget | `compaction-audit-every-module` fails —
  end state correct, `compaction_events == 0` | | Resume reconciliation | the killed run leaves the
  suite red; the resumed one does not |

The compaction row is the one worth staring at. With the budget removed the agent does the same work
  and leaves an **identical, correct** end state. The task fails only because compaction never fired
  — exactly the coverage claim a file-only grader would get wrong.

## Two bugs found in the machinery built to find bugs

Both were live, both silent, both in the direction that loses failures:

- **A bound typo asserted nothing.** `{"minimum": 1}` parsed as a bound with no ends, which passes
  for *any* value. The requirement read as asserted in the task file and checked nothing. Unknown
  keys are now refused. - **A grader that raised scored as a pass.** Merging two verdicts recomputed
  `passed` from the combined checks — and a grader that threw reports a reason with no checks, so
  the merge read the empty list as "nothing failed".

## Does the suite discriminate?

A scripted oracle that writes byte-perfect solutions for all 22 tasks passes **16**. It fails every
  compaction and permissioning task, because producing the right files is not what those categories
  measure. The recovery tasks pass, which means the kill-and-resume path genuinely ran.

The existing both-directions check was extended to cover requirements, so all 22 tasks are still
  bracketed between "did nothing" and "did it perfectly".

## Verification

- **344 tests, 98% coverage**, ruff / `ruff format` / `mypy --strict` / docs `--strict` clean - All
  22 tasks run in real containers (Docker 29.7.2), zero harness errors

## Deviation from the plan

Recovery tasks assert that the task's own graders pass after a kill and resume, rather than
  comparing tree hashes against a second uninterrupted run. Two runs of a real model differ for
  reasons that have nothing to do with recovery, so hash equality is only meaningful with a scripted
  provider — where it already lives, in `tests/test_recovery.py`.

## Not done here

The flake-rate metric still needs a real model run. Both determinism checks use a scripted provider,
  which proves the harness adds no variance but says nothing about model variance.


## v0.1.0 (2026-08-13)

### Bug Fixes

- Release as the deploy key, and stop the docker probe blocking
  ([#11](https://github.com/alvarodiez20/endstate/pull/11),
  [`6cc7bcc`](https://github.com/alvarodiez20/endstate/commit/6cc7bcc57162580cc6f65865438024db6255a0fa))

The v0.1.0 release failed at `git push`. Nothing was published — no tag, no GitHub Release, PyPI
  still at 0.0.1 — so no version number was burned. This unblocks it, and fixes a second thing the
  attempt exposed.

## The release could not push

``` remote: error: GH013: Repository rule violations found for refs/heads/main.

remote: - Changes must be made through a pull request. ```

The `main` ruleset requires a PR and green checks, and its single bypass actor is the release deploy
  key. The job checks out with that key — but semantic-release builds its own push URL from
  `GITHUB_TOKEN` and pushes to *that*, ignoring the SSH remote the checkout configured. So the push
  arrives as the token, which is not a bypass actor.

`ignore_token_for_push = true` under `[tool.semantic_release.remote]` makes it push over the
  configured remote instead.

**This had been broken since the release pipeline landed, and stayed green the whole time.** Runs
  that release nothing never push, so every `docs:` and `chore:` merge exercised everything *except*
  the one step that was wrong. It could only surface on the first `feat:` — which is to say after
  the merge, with the version already owed. CONTRIBUTING now says so, because the next person to
  touch this deserves to know it fails silently.

## The Docker probe blocked for 20 seconds

Found while verifying the above, and worth fixing before v0.1.0 because it is user-facing:

- `docker_available()` gates `endstate eval --sandbox docker`. With no daemon — or a wedged one —
  the CLI sat for 20s before reporting it. - It is also a `skipif` condition. Those are evaluated at
  import, once per decorator, so a machine without Docker paid the timeout twice on every test run.

Now 5s, which is generous for a command a healthy daemon answers in milliseconds; every slower case
  answers False anyway. The test module holds the probe result in one constant rather than calling
  it per decorator.

Deliberately **not** cached in the function: a daemon can start or stop between calls, and a stale
  `False` would quietly route an eval run to the local sandbox — which is not an isolation boundary.
  A test pins the timeout so it cannot drift back.

Local suite with no daemon running: **42s → 7.7s**.

## Verification

- 257 tests, zero skipped, with a live daemon — both Docker integration tests run - ruff, `ruff
  format`, `mypy --strict`, docs `--strict` all clean

Titled `fix:` so it is a patch on its own; the pending `feat:` from #10 still drives the bump, so
  merging this should cut **v0.1.0**.

### Chores

- Support every Python version python.org still supports
  ([#5](https://github.com/alvarodiez20/endstate/pull/5),
  [`a24d762`](https://github.com/alvarodiez20/endstate/commit/a24d762e368a4b5a1536aa6eb89512bae6514ed0))

Widens the supported range from 3.11–3.13 to **3.10–3.14** — every version python.org currently
  lists as supported.

`enum.StrEnum` (3.11+) was the only thing standing in 3.10's way. `src/endstate/_compat.py`
  backports it in four lines, taking `str.__str__` explicitly: subclassing `str, Enum` alone is not
  equivalent, because on 3.11+ that renders as `Decision.ALLOW` where real `StrEnum` renders as
  `allow` — the members end up in logs, denial reasons and JSON payloads, so that difference would
  have been a silent behaviour change between versions.

3.14 needed no code changes at all.

- `requires-python`, classifiers, `ruff target-version` and `mypy python_version` all move to the
  floor of the range, so the linter and type checker analyse against the oldest version supported
  rather than the newest. - CI matrix goes from 3 jobs to 5. - Verified locally on 3.10, 3.11 and
  3.14: `pytest`, `mypy --strict`, `ruff`, and the ≥85% coverage gate (96.4%).

**3.10 goes security-only in October 2026**, two months out; the matrix comment says to drop it
  then.

### On the title

This is titled `chore:` deliberately, so merging cuts no release. Broadening the supported range is
  arguably a `feat:`, and if it should ship as 0.1.0 then retitle before merging — squash uses the
  title at merge time. Worth knowing what that implies: 0.1.0 would also carry the unreleased M1
  work and publish to PyPI unattended, since the `pypi` environment has no reviewer gate.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-authored-by: Claude Opus 5 <noreply@anthropic.com>

### Continuous Integration

- Automate versioning and PyPI publishing, adopt trunk-based development
  ([#1](https://github.com/alvarodiez20/endstate/pull/1),
  [`1f7bc9d`](https://github.com/alvarodiez20/endstate/commit/1f7bc9d68adef1bd2ada5208053109187d0d0298))

## What this changes

Automated semver versioning and PyPI publishing, plus trunk-based development settings.

**One workflow, two jobs.** `release.yml` runs after `ci` succeeds on `main`. The `version` job uses
  python-semantic-release to compute the bump from Conventional Commits, update `__version__`, write
  `CHANGELOG.md`, tag, and cut a GitHub Release. If it cut one, the `publish` job builds from that
  tag and uploads to PyPI via Trusted Publishing. Both live in one file because PyPI's trusted
  publisher is bound to a workflow *filename* — publishing from anywhere else fails the OIDC check.

**So a merged `feat:` or `fix:` reaches PyPI without anyone pressing anything.** To put a human in
  front of that, add a required reviewer to the `pypi` environment in repository settings; the
  publish job will then wait for approval, and no workflow file changes. To re-publish an existing
  tag after a failed upload, run `release` manually with the tag as input — the build's version is
  checked against the tag before upload, and `skip-existing` keeps a re-run from failing on what is
  already there.

**Releases only ever tag a commit that passed CI.** `ci` goes green on one specific commit, but
  `main` may have moved by the time this workflow starts. The `version` job compares `HEAD` against
  `workflow_run.head_sha` and stands down when they differ, leaving the release to the newer
  commit's own `ci` run — which covers both. Without that check, two merges landing close together
  could tag a commit whose tests had not finished.

**Single source of truth.** The version was in both `pyproject.toml` and `__init__.py`. `pyproject`
  now declares it `dynamic` and hatchling reads `__init__.py`, so release automation edits one file.

**Trunk-based development.** `main` requires linear history, blocks force pushes and deletions;
  merge commits disabled repo-wide; branches auto-delete on merge; squash commit message defaults to
  the PR title.

**Docs.** Removed the edit-file icon.

## Why

Hand-managed version numbers drift, and the two copies of `0.0.1` were already an accident waiting
  to happen.

## How it was verified

python-semantic-release 9.21.2 run against a clone of this repo with the real config:

| Commit | Next version | | --- | --- | | `docs:` / `chore:` | no release | | `fix:` | 0.1.1 | |
  `feat:` | 0.2.0 | | `feat!:` | 0.2.0 — not 1.0.0 |

Confirmed it rewrites `__version__`, that `uv build` then produces the bumped artifact, and that the
  release commit carries `[skip ci]`. Workflow YAML parsed. `make check` and `make docs-build
  --strict` green.

Re-checked against `main` as it stands today: everything since `v0.0.1` is `docs:`, `ci:`, or
  non-conventional, so **merging this PR cuts no release** — correct behaviour, and a live test of
  the rule. The first `feat:` after it will cut 0.1.0 and carry the unreleased M1 work with it.

> **A PyPI version number can never be reused.** Not after a yank, not after a delete.

## Added since first review

**Releases only tag a commit `ci` actually passed on.** `ref: main` is HEAD at the moment the
  workflow starts, not the commit whose `ci` run triggered it; two merges landing close together
  could put the tag on a commit whose tests had not finished. The `version` job now compares `HEAD`
  with `workflow_run.head_sha` and stands down when they differ — the newer commit's own `ci` run
  releases both.

**`main` has a ruleset:** pull request required (0 approvals), `check (3.11/3.12/3.13)` required to
  merge, squash and rebase only. Docs `build` is deliberately *not* required — `docs.yml` is
  path-filtered, so on a PR that touches no docs it would never report and the PR could never merge.

**The release pushes with a deploy key.** Rulesets apply to Actions too, so `GITHUB_TOKEN` can no
  longer push the version commit or tag to `main`. A deploy key is the ruleset's one bypass actor;
  the `version` job checks out over SSH with `RELEASE_SSH_KEY` and fails on its first step, with an
  explicit message, if that secret is missing. Setup and rotation commands are in CONTRIBUTING.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

---------

Co-authored-by: Claude Opus 5 <noreply@anthropic.com>

### Documentation

- Add a "Copy page" button, and badges on the docs home
  ([#6](https://github.com/alvarodiez20/endstate/pull/6),
  [`644ffc6`](https://github.com/alvarodiez20/endstate/commit/644ffc665a6674d343eafcdb5104cfa2c569dd4e))

Two things.

### Copy page

Every page gets a button that copies its **Markdown source**, not the rendered text — the source
  keeps the code fences, tables and admonitions, which is the form actually worth pasting into a
  model or an issue.

The source comes from this site rather than from GitHub: `hooks/page_source.py` writes each page's
  Markdown beside it in the build output as `<path>.md.txt`, and `overrides/main.html` points the
  button at it with `base_url`. That means it works on a local `mkdocs serve` and in an offline
  build, and it does not hardcode a branch name or depend on raw.githubusercontent being reachable.
  The `.txt` suffix is load-bearing twice: MkDocs would otherwise treat a `.md` in the output tree
  as a page to render, and GitHub Pages would serve an unknown extension as a download instead of
  inline text.

21 source files, 21 `.md.txt` files emitted — the two excluded READMEs (brand, diagrams) correctly
  produce none.

Verified in a browser: a real click fetches 5,088 characters for `concepts/the-loop`, starting `#
  The loop`, fences intact, and the button reports `Copied`. On failure it says so and logs the
  reason rather than silently doing nothing — a clipboard write needs a secure context, which a
  `file://` build does not have.

This adds `theme.custom_dir`, so the site now carries a theme override. It extends `base.html` and
  touches one block, which is the cheapest form that exists, but it is a coupling to Material's
  template names worth knowing about.

### Badges

The same seven as the README, under the lockup on the docs home.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-authored-by: Claude Opus 5 <noreply@anthropic.com>

- Add part two, the five problems around the loop
  ([#7](https://github.com/alvarodiez20/endstate/pull/7),
  [`010deb7`](https://github.com/alvarodiez20/endstate/commit/010deb7174bd7117404657ed497d80aaaedc6927))

Expands `docs/concepts/` from eight pages to thirteen: skills, MCP and tool discovery, memory,
  subagents, and prompt injection. Each is something this harness does **not** implement and any
  deployed agent hits anyway, so each opens with a status box saying so and cites its sources at the
  bottom.

### Corrections found while auditing the claims

Every figure was checked against the cited source. Six did not survive:

| Claim | Problem | Now | | --- | --- | --- | | Model Armor `0% / 90%` | Mixed two rows of the
  paper's table — 0% static is the GPT-5 Mini row, 90% adaptive is Gemini-2.5 Pro | `28% / 90%`,
  both Gemini-2.5 Pro, with the model and benchmark stated | | StruQ `62%` static | Appears nowhere
  in the paper; StruQ was run on a different benchmark with no static figure | Cut; adaptive result
  kept as the paper words it | | Circuit Breaker `8%` static | Same — HarmBench, no static figure
  given | Cut; `100%` adaptive is confirmed verbatim | | "is this better than spending 15× on a
  single agent?" | 15× is Anthropic's multiplier against a *chat*; single agents are already 4× a
  chat, so multi-agent is ~4× a single agent | Reworked to compare against the single agent you
  would otherwise build, with the 3–10× figure from Anthropic's later guidance | | The
  tool-ambiguity block quote | Not traceable to a primary source; the closest published wording
  differs | Restated as the page's own claim, not a quotation | | "the disposable container… is
  real" | It is planned for v0.1.0 — as the body of that same page says four screens later | Status
  box now matches the body |

The GitHub MCP exploit is also now named and dated (Invariant Labs, May 2025) with the actual leak
  channel (a pull request), and the red-team row is qualified: 100% is over the subset of scenarios
  that competition covered, against 69% for the automated search attack.

**Verified and left as written:** 150,000 → 2,000 tokens and 98.7%; 90.2% and the 80% BrowseComp
  variance; 1,000–2,000 tokens returned per subagent; every Agent Skills frontmatter constraint and
  the three disclosure levels; the Rule of Two wording; Willison's catalogue of affected products;
  the Pokémon example, which is verbatim accurate down to the 1,234 steps.

### The concepts map

Kept scoped to the eight. The diagram's mechanic is "hover a card to see which loop step it attaches
  to", and the five new pages do not attach at a single point — that is *why* they are a separate
  list. The subtitle now reads `part one — eight problems, one loop`, a strip under the cards names
  the five that sit around the loop, and `index.md` says the same thing in prose.

### Verification

`mkdocs build --strict` exits clean with no `WARNING` or `ERROR` lines. All 0 broken relative links
  across the whole docs tree, and all 22 links into `src/` resolve to files that exist. Checked the
  rendered pages in a browser, light and dark.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-authored-by: Claude Opus 5 <noreply@anthropic.com>

- Add status badges to the README ([#4](https://github.com/alvarodiez20/endstate/pull/4),
  [`150f23f`](https://github.com/alvarodiez20/endstate/commit/150f23f55d5052bca09cfb971ec7e4a9c6fffeac))

Seven badges under the lockup: `ci`, `docs`, PyPI version, supported Pythons, licence, ruff, and
  `mypy --strict`. All absolute URLs, since this file is also the PyPI long description and PyPI
  resolves nothing relative. Each was fetched and confirmed to render before committing; `twine
  check` passes on both the wheel and the sdist.

Also adds the `Programming Language :: Python :: 3.13` classifier. CI has gated on 3.13 since M0,
  but the published metadata claimed 3.11 and 3.12 only — and the pyversions badge reads the
  metadata, not the test matrix, so it currently understates support. The badge corrects itself at
  the next release; this PR is titled `docs:` on purpose and cuts none.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-authored-by: Claude Opus 5 <noreply@anthropic.com>

- Add the remaining nine diagrams, and a skill examples page
  ([#9](https://github.com/alvarodiez20/endstate/pull/9),
  [`dea2e70`](https://github.com/alvarodiez20/endstate/commit/dea2e702fefee1eacb26325581ef8c20cf0e6de4))

## What this changes

Adds the remaining nine animated diagrams, completing the set at eighteen — one for every concept
  page, plus the home page, both getting-started pages, and the decision log.

New: `hero`, `first-run`, `resuming`, `decisions`, `skills`, `subagents`, `memory`,
  `mcp-and-tool-discovery`, `prompt-injection`. The nine existing diagrams are untouched.

Also lands the `Skill examples` page, which was already in the working tree — kept as its own commit
  so the two are reviewable apart.

## Why

Part two shipped in #7 without diagrams, and the pages that carry the actual argument — the home
  page and the decision log — had none at all. The five part-two concepts are the ones where a
  picture does the most work: the lethal trifecta, progressive disclosure, and the 150k-to-2k schema
  collapse are all shape arguments.

Two things worth a reviewer's attention:

- **The new files are patched to match the existing nine.** The upstream copies serve React from
  unpkg, set `color-scheme` only on `documentElement`, and autoplay unconditionally. Each new file
  got the same three local changes the existing ones carry: React from `vendor/` via
  `window.__resources`, the `document.body` half of the theme bridge, and a `prefers-reduced-motion`
  guard on autoplay. Without these the docs would make a third-party request on every page view and
  the diagrams would ignore the palette toggle. - **Heights are measured, not copied.** The numbers
  suggested upstream were off by up to 140px. Each diagram's `scrollHeight` was sampled at 120ms
  intervals through a full animation cycle at the 688px Material column, then given the same ~40px
  of slack the existing embeds use. `skills` is 760, not the suggested 620.

Placement follows the existing convention — after the intro prose, after the `!!! info "Status"`
  admonition where there is one, before the first `##`. Two deliberate exceptions: `first-run` sits
  after the run summary table it annotates rather than at the top of a page that opens straight into
  a `##`, and `hero` sits after the status warning on the home page.

## How it was verified

- `mkdocs build --strict` clean. - All eighteen iframe `src` paths resolved against the built site —
  200 on every one. This is the real risk in this change: `docs/index.md` needs `assets/diagrams/`,
  everything under `concepts/`, `getting-started/` and `design/` needs `../../`, and
  `concepts/index.md` needs `../`. All three forms are present and all three were checked, not
  reasoned about. - Each new diagram mounts (React renders, `.sc-host` present) and follows the
  Material light/dark toggle in **both** directions — verified by loading the built site under each
  scheme and reading `colorScheme` inside the iframe, not just eyeballing one of them. - No unpkg
  requests recorded while the diagrams rendered, which is the point of the `__resources` patch. - No
  console errors.

The upstream `INTEGRATION.md` is deliberately not committed: it is a paste guide for the delivery
  folder, and its instructions conflict with this repo's conventions on wrapper markup, relative
  paths, and heights. `docs/assets/diagrams/README.md` already covers this ground and has been
  updated from "nine" to "eighteen".

---------

Co-authored-by: Claude Opus 5 <noreply@anthropic.com>

- Animate the eight concepts ([#2](https://github.com/alvarodiez20/endstate/pull/2),
  [`f792e64`](https://github.com/alvarodiez20/endstate/commit/f792e64b466af5a547e15b0941e22aced15e11f6))

Adds a self-contained animated diagram to each page in `docs/concepts/`, embedded as an iframe that
  steps through the mechanism the page describes.

### Notes for review

- **React is vendored, not fetched from a CDN.** The diagram runtime loads React 18.3.1 from unpkg
  by default; a docs site making a third-party request on every page view is not something to ship,
  so the two UMD builds live in `docs/assets/diagrams/vendor/` and each diagram points the runtime's
  own `__resources` override at them. They were verified against the SRI hashes the runtime pins —
  hashes and the re-verify command are in `docs/assets/diagrams/README.md` (excluded from the built
  site). - **Sizing.** Each embed is a fixed-height iframe in a `.endstate-diagram-scroll` wrapper.
  Heights were measured against the tallest animation frame at the ~688px Material content column,
  with 24–67px slack. Below ~680px the wrapper pans horizontally rather than letting the layouts
  collapse. - **`iframe src` is not rewritten by MkDocs** the way `<a href>` and `<img src>` are, so
  the paths are relative to the rendered URL: `../../assets/…` from the sub-pages, `../assets/…`
  from `concepts/index.md`. - **Theming.** `embed.js` pushes the Material palette scheme into each
  iframe, so the diagrams follow the toggle rather than only the OS setting — including across
  `navigation.instant` navigations. - **Motion.** Autoplay starts paused when
  `prefers-reduced-motion: reduce` is set; every diagram also has play/pause and step controls.

### Verification

`mkdocs build --strict`, `ruff check`, `ruff format --check`, `mypy`, and `pytest` all pass. All
  nine diagrams were checked in a browser in light and dark, at the desktop content width and
  narrower: no clipping, no horizontal overflow, and no requests off-origin apart from the Google
  Fonts stylesheet the theme already loads.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-authored-by: Claude Opus 5 <noreply@anthropic.com>

- Give each part-one concept an open-problems section
  ([#8](https://github.com/alvarodiez20/endstate/pull/8),
  [`b5bfba4`](https://github.com/alvarodiez20/endstate/commit/b5bfba44b203c9ad89234876ffef497542aef992))

Each of the eight part-one pages now closes with **Open problems**: what is still unsolved about
  that concept, what the current best practice is, and which of this harness's decisions are bets
  rather than settled answers. They cite sources inline, because unlike the rest of those pages they
  are not describing code in this repository — and `concepts/index.md` says they are the most likely
  part of these docs to go stale.

### Corrections found while auditing the claims

Every figure was checked against its cited source. Three did not survive as written:

| Claim | Problem | Now | | --- | --- | --- | | Tokens go on the `gen_ai.client.token.usage` metric;
  conventions moved repos "in v1.42.0 (June 2026)" | The GenAI spans doc records tokens as **span
  attributes** — and splits cache creation from cache read, which is exactly the split this module
  doesn't make. The move happened, but I could not confirm the version or date. | Span attributes
  named individually; the move stated without a version | | Thinking retention: "Opus 4.5 and models
  numbered 4.6 and higher … Sonnet 4.5, Haiku 4.5 and earlier stripped it" | The boundary falls in a
  **different place per family** — Opus ≥ 4.5, Sonnet ≥ 4.6 — and the non-retaining models keep the
  *last* turn, not nothing | Stated per family, with the model-switch rule added: switching models
  means stripping thinking yourself, or paying for tokens the new model silently ignores | | "Cursor
  audited 731 successful trajectories … 63% had retrieved the fix" | The auditor examined 731
  trajectories **blind to whether each passed**; the 63% is of the successful resolutions among them
  | Both numbers stated in their own terms; also added that GPT models did not show the same
  escalation |

### Verified and left as written

The whole `how-we-contain-claude` block is verbatim-accurate: 93% of permission prompts approved,
  84% reduction after the OS sandbox, 0.4% benign-blocked and ~17% overeager-through for the
  auto-approver, **24 of 25** on the credential-exfiltration red team,
  symlink-resolution-before-path-validation, the three containment patterns, the `api.anthropic.com`
  Files API exfiltration, and the EDR-visibility tradeoff. Also verified: Chroma's 18 models and the
  shuffled-beats-coherent finding, METR's ~7-month doubling over six years (plus the live-chart
  caveat, which METR's own post now endorses), Ord's constant-hazard half-life and his "unknown
  whether it generalises" caveat, the 3×/6× SWE-bench-Verified contamination multiples, and Cursor's
  87.1→73.0 / 74.7→54.0 sealed-harness numbers.

### Verification

`mkdocs build --strict` exits clean with no `WARNING` or `ERROR` lines. Zero broken relative links
  across the docs tree; all 22 links into `src/` resolve.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-authored-by: Claude Opus 5 <noreply@anthropic.com>

- Warn that a PR body can silently disable CI
  ([#3](https://github.com/alvarodiez20/endstate/pull/3),
  [`51fb2a7`](https://github.com/alvarodiez20/endstate/commit/51fb2a7bb26a47f5d35812061a781c3871db03f2))

Squash-merge puts the PR body into the commit message, and GitHub scans the entire message — body
  included — for its skip markers. A PR that mentions one in prose merges into a commit that runs
  **no workflows at all**: no `ci`, no `docs` deploy, no release evaluation, and nothing reports a
  problem anywhere.

This is not hypothetical. It happened on the merge of #1, whose body quoted the marker while
  describing the release commit. That merge ran nothing; the site was rebuilt by dispatching `docs`
  by hand.

Adds a note to CONTRIBUTING.md next to the existing "PR title becomes the commit message" warning,
  with the marker written defensively so this PR does not repeat the trick.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-authored-by: Claude Opus 5 <noreply@anthropic.com>

### Features

- Grade the end state of a sandbox with an eval runner and 12 tasks
  ([#10](https://github.com/alvarodiez20/endstate/pull/10),
  [`9e88b31`](https://github.com/alvarodiez20/endstate/commit/9e88b31dcb9f2aee64b3b2aa73b81bc1a9da3b3f))

Closes M2. `endstate eval --suite tasks/` runs an agent in a disposable container per task and
  grades what it left behind.

```bash endstate eval --suite tasks/ --model gpt-4o-mini --jobs 4 --out benchmarks/ ```

## The contract is enforced, not documented

```python def grade(sandbox: Sandbox) -> Verdict: ... ```

Graders resolve from a dotted path, and resolution inspects the signature: the first parameter must
  be a positional `sandbox`, and `messages` / `transcript` / `result` / `history` are refused
  outright. A grader that *can* read the transcript eventually gets written to check the transcript
  — someone adds "and it mentioned running the tests" because it is easier than checking that they
  ran. Conventions erode; signatures do not.

## The end state can be gamed too

Removing the fluency exploit is not the same as removing every exploit. Editing the tests satisfies
  "the suite is green" completely. Every one of the twelve tasks therefore also asserts:

| Hack | Grader | | --- | --- | | Edited the tests | `files_unchanged` | | Skipped the test |
  `no_new_skips` | | Special-cased the input | `holdout/`, staged in after sealing | | Deleted
  something inconvenient | `changed_paths_within` |

Held-out tests are files, so staging them changes the tree. The runner **seals** the end state the
  moment the agent stops — otherwise every tree assertion would be made against a tree the grader
  itself had just modified.

## How we know the graders test anything

Each task ships a `solution/` no agent ever sees, and `tests/test_suite.py` asserts both directions
  for all twelve:

- graders **fail** on the untouched fixture — 12/12 - graders **pass** on the reference solution —
  12/12

This earned its keep while the suite was being written: several graders passed on the unsolved
  fixture on the first attempt, and two rejected their own reference solution. Neither is visible by
  reading the task definition.

## Also in here

- **`Tool.idempotent`**, the M1 follow-up. Resume no longer replays an outstanding call to a
  non-idempotent tool (`bash`); it answers "outcome unknown, check the state before retrying" so the
  conversation stays well-formed without committing a second side effect. - **`.git` is stripped
  from every fixture.** A task built from a real repository ships the answer inside it, and `git
  log` is cheaper than solving the problem. - **Rich markup escaping in the CLI.** `pip install
  'endstate[openai]'` was rendering as `pip install 'endstate'` — bracketed content in grader
  reasons was being silently deleted from eval output.

## Verified against a real daemon

Docker Desktop 29.7.2, `python:3.12-slim`:

| | | | --- | --- | | Network egress | blocked (`create_connection` to 1.1.1.1 fails) | | Bind mount
  | live in both directions | | Containers left behind | none | | Suite | 12/12 in 1.6s at `--jobs
  4`, identical verdict vector across runs |

Two integration tests assert this and skip when no daemon is reachable, so CI runs them.

**256 tests · 98% coverage · mypy strict clean · docs build strict.**

## Deviations from the plan

- `Task.grader: str` became `graders: list[GraderSpec]`. Every interesting task is a conjunction —
  did the work *and* did not cheat — and a list makes that the only available shape. - 12 tasks, not
  10. The 5 + 4 + 3 breakdown always summed to 12; the heading was wrong. -
  `tests/test_provider_contract.py` moved from M2 to M4. It is meaningless until there are three
  adapters to compare.

## Not done here

Flake rate over three consecutive runs is still unmeasured — both determinism checks use a scripted
  provider, which proves the harness adds no variance but says nothing about model variance. That
  needs an API key and three real runs.

## Note before merging

This is a `feat:`, so merging cuts **v0.1.0** and publishes to PyPI automatically. A PyPI version
  can never be reused, so merge when you mean to ship.


## v0.0.1 (2026-08-11)
