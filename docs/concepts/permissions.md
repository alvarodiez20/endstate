# Permissions and refusal

An agent that cannot be stopped is not deployable. This page is about making "the agent refused" into
an outcome your system produces on purpose and your tests can assert on.

<div class="endstate-diagram-scroll">
  <iframe class="endstate-diagram" src="../../assets/diagrams/permissions.html"
          height="620" loading="lazy" title="How a permission decision is reached"></iframe>
</div>

## The asymmetry

Start here, because every other decision on this page follows from it:

> A wrongly denied command is an annoyance. A wrongly allowed one is an incident.

Those two errors are not symmetric, so the policy that treats them symmetrically is wrong. Which
means the default has to be **deny**, and everything the agent is allowed to do has to be stated.

This is unpopular because it is more work up front and it produces friction during development. It is
also the only version that fails safe when the model does something nobody anticipated — which is the
entire category of problem you are defending against, since if you could anticipate it you would have
just prevented it.

## The policy

Rules are checked in order and the first match wins:

```python
class Rule(BaseModel):
    tool: str = "*"                        # tool name, or '*' for any
    argument_pattern: str | None = None    # regex over the serialised arguments
    decision: Decision = Decision.DENY
    reason: str = ""

class PermissionPolicy(BaseModel):
    rules: list[Rule]
    default: Decision = Decision.DENY

    def check(self, tool: str, arguments: dict[str, Any]) -> tuple[Decision, str]:
        for rule in self.rules:
            if rule.matches(tool, arguments):
                return rule.decision, rule.reason
        return self.default, "no matching rule"
```

Source:
[`agent/permissions.py`](https://github.com/alvarodiez20/endstate/blob/main/src/endstate/agent/permissions.py).

`Decision` has three values, not two: `ALLOW`, `DENY`, and `ASK`. The third is what a human-in-the-loop
deployment needs — the call is neither safe enough to run unattended nor wrong enough to refuse. It is
in the type from the start because retrofitting a third state into a boolean is miserable.

## Ordering is the whole design

The default policy denies destructive patterns *first*, then allows tools generally:

```python
Rule(tool="bash", argument_pattern=DESTRUCTIVE_SHELL, decision=DENY, ...)
Rule(tool="bash", argument_pattern=GIT_DESTRUCTIVE,   decision=DENY, ...)
Rule(tool="bash", argument_pattern=SECRET_EXFIL,      decision=DENY, ...)
Rule(tool="read",  decision=ALLOW)
Rule(tool="write", decision=ALLOW)
Rule(tool="bash",  decision=ALLOW)     # only reached if no deny matched
```

Flip the last line above the first three and the policy still passes a naive "does it allow bash?"
test while permitting `rm -rf /`. First-match-wins with denies at the top is not a style preference;
it is the property that makes the policy mean anything.

## What gets denied by default

Three families, kept deliberately short — a deny-list nobody understands is a deny-list nobody
maintains.

| Family | Catches |
| --- | --- |
| `DESTRUCTIVE_SHELL` | `rm -rf` and variants, `mkfs`, `dd if=`, fork bombs, `chmod -R 777 /`, writes to `/dev/sd*`, `shutdown`/`reboot`/`halt` |
| `GIT_DESTRUCTIVE` | `push --force`, `push -f`, `reset --hard origin`, `branch -D` |
| `SECRET_EXFIL` | `curl`/`wget`/`nc` in the same command as `$*_KEY`, `$*_TOKEN`, `.env`, `id_rsa`, `credentials` |

The third one is the interesting category and the one most policies miss entirely. Destructive
commands are loud and you will notice them. Exfiltration is quiet — a `curl` that posts your `.env`
to a pastebin looks like ordinary network activity and produces no error, no missing file, and
nothing in the transcript that reads as alarming.

!!! warning "A deny-list is a speed bump, not a wall"

    `rm -rf /` is caught. `python -c "import shutil; shutil.rmtree('/')"` is not. Base64-encoded
    payloads are not. A model determined to be clever will get past any regex, and so will a
    [prompt injection](prompt-injection.md) in a file the agent reads.

    The deny-list is layer 2. Layer 1 is the [disposable container](tools-and-sandbox.md), and it is
    the only one that is really a boundary. Treat the regexes as protection against plausible
    accidents, not against adversaries.

## The subtle bug in the pattern list

Worth reading the comment in the source, because it is a real trap:

```python
# These are plain (non-verbose) regexes on purpose. Rules accept user-supplied
# patterns, so compiling with re.VERBOSE would silently change the meaning of
# anyone else's pattern containing a literal space or '#'.
```

The obvious way to write a long pattern list is `re.VERBOSE`, so you can space it out and comment it.
But `Rule.argument_pattern` is user-supplied, and it is compiled by the same code path. Turn on
`re.VERBOSE` and every user pattern containing a space stops matching what its author meant — silently,
with no error, in the direction of allowing things. A formatting preference turns into a security
regression.

## Denial is a first-class result

When a call is denied, the loop does not raise. It records a `DeniedCall`, opens a `tool.denied`
trace span, and feeds a result back to the model:

```
permission denied (deny): destructive filesystem or system command
```

Three consequences, all of them the point:

1. **The agent can adapt.** It sees the refusal and can try a safe alternative, which is what a
   competent colleague would do.
2. **The run continues.** One refused command does not throw away twenty steps of correct work.
3. **`denied_calls` ends up in `RunResult`,** which means an eval can assert on it.

That last one is what makes refusal testable. A permissioning task passes when three things hold
together: the destructive request was refused, `denied_calls >= 1`, and the sandbox tree hash is
unchanged. You are asserting that nothing happened — and "nothing happened" is only checkable if the
harness records the near-miss and the grader can look at the filesystem.

## Proving the policy is load-bearing

A test suite that passes whether or not a feature works is decoration. The plan for M3 includes a
mutation check: disable the permission policy, and the permissioning eval tasks must **fail**. If
they still pass, they were never testing the policy.

Run that check against your own guardrails. It is uncomfortable and it is the only way to know.

*(Mutation check planned for M3 — see the
[engineering plan](https://github.com/alvarodiez20/endstate/blob/main/PLAN.md).)*

## Writing your own

See [Write a permission policy](../guides/permission-policy.md).

For *why* the `SECRET_EXFIL` family exists and why cutting the outbound channel is the highest-value
rule in the whole policy, see [Prompt injection and the lethal trifecta](prompt-injection.md).
