# Contributing

## Trunk-based development

`main` is the trunk. It is always releasable, and it is the only long-lived branch — there is no
`develop`, no release branches, no `next`.

Work happens on short-lived branches cut from `main` and merged back within a day or two. A branch
that lives for a week has stopped being a feature branch and started being a fork.

```bash
git switch main && git pull
```

```bash
git switch -c fix-compaction-pinning
```

```bash
git push -u origin HEAD && gh pr create
```

## History is linear

`main` enforces linear history, so merge commits cannot land on it. Two ways to merge a PR, both of
which keep it that way:

- **Squash and merge** — the whole branch becomes one commit. Default choice, and the right one for
  most changes.
- **Rebase and merge** — each commit is replayed onto `main`. Use when the individual commits are
  worth keeping.

Merge commits are disabled at the repository level, and force-pushing or deleting `main` is blocked.

Keep a branch current by rebasing, never by merging `main` into it:

```bash
git pull --rebase origin main
```

This repository's local git config already sets `merge.ff = only`, `pull.rebase = true` and
`rebase.autoStash = true`, so the default commands do the right thing.

## Commit messages decide the version

Releases are automated from [Conventional Commits](https://www.conventionalcommits.org/). The message
is not paperwork — it is the input that picks the next version number.

| Prefix | Effect | Example |
| --- | --- | --- |
| `feat:` | minor bump | `feat: add the eval runner` |
| `fix:` | patch bump | `fix: stop compaction dropping the task statement` |
| `perf:` | patch bump | `perf: hash the tree in one pass` |
| `docs:` `chore:` `test:` `refactor:` `ci:` `style:` `build:` | **no release** | `docs: explain the mutation check` |
| `feat!:` or a `BREAKING CHANGE:` footer | major bump — but see below | `feat!: change the Tool signature` |

Anything that matches no prefix produces no release, which is the intended outcome rather than a
failure. Documentation and chores land on `main` without consuming a version.

> **Pre-1.0 exception.** `major_on_zero` is off, so a breaking change bumps the **minor**: `0.1.0`
> becomes `0.2.0` rather than `1.0.0`. Reaching v1.0.0 is a decision this project makes deliberately,
> not one that a `feat!:` makes by accident.

**When squash-merging, the PR title becomes the commit message.** So the convention applies to PR
titles too — a PR titled "Fix the thing" produces no release no matter what its commits say.

## What happens when you merge

1. `ci` runs the gates on 3.11, 3.12 and 3.13: ruff, `ruff format --check`, `mypy --strict`, pytest,
   coverage ≥ 85%.
2. If CI passes on `main`, `release` computes the bump from the commits since the last tag. If there
   is one, it updates `__version__`, writes `CHANGELOG.md`, commits, tags, and cuts a GitHub Release.
3. If a release was cut, the same workflow builds from that tag and publishes to PyPI via Trusted
   Publishing. The build's version is checked against the tag first.
4. `docs` rebuilds and deploys the site.

So a merged `feat:` or `fix:` reaches PyPI without anyone pressing anything. Two consequences worth
holding in mind:

- **A PyPI version number can never be reused.** Not after a yank, not after a delete. If a bad
  release ships, the fix is `0.1.1`, not a re-upload of `0.1.0`.
- **Commit messages are now a release mechanism.** `fix:` on a branch that is not ready ships that
  code. `chore:` or `refactor:` land safely without a version.

To put a human in the loop without changing any workflow, add a required reviewer to the `pypi`
environment in repository settings — the publish job will then wait for approval.

To re-publish an existing tag (a failed upload, a transient PyPI outage), run the `release` workflow
manually and give it the tag.

## Before you push

```bash
make check
```

Lint, format, types and tests — the same four gates CI runs. It takes about a second.

```bash
make docs-build
```

Builds the docs with `--strict`, so a broken internal link fails the build rather than shipping.
