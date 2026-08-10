"""Permission policy for tool calls.

An agent that cannot be stopped is not deployable. This module exists so that
"the agent refused" is a testable outcome: eval tasks in the permissioning
category pass only when a destructive request is denied and the sandbox is
unchanged.

Rules are evaluated in order; the first match wins. Default is DENY for anything
not explicitly permitted, because the failure modes are asymmetric.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Decision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class Rule(BaseModel):
    """Match a tool call by tool name and optionally by argument content."""

    tool: str = "*"
    """Tool name, or '*' for any."""

    argument_pattern: str | None = None
    """Regex matched against the serialised arguments. None matches anything."""

    decision: Decision = Decision.DENY
    reason: str = ""

    def matches(self, tool: str, arguments: dict[str, Any]) -> bool:
        if self.tool != "*" and self.tool != tool:
            return False
        if self.argument_pattern is None:
            return True
        blob = " ".join(str(v) for v in arguments.values())
        return re.search(self.argument_pattern, blob, re.IGNORECASE) is not None


# Patterns that must never run unattended. Kept deliberately short and readable:
# a deny-list nobody understands is a deny-list nobody maintains.
#
# These are plain (non-verbose) regexes on purpose. Rules accept user-supplied
# patterns, so compiling with re.VERBOSE would silently change the meaning of
# anyone else's pattern containing a literal space or '#'.
DESTRUCTIVE_SHELL = "|".join(
    [
        r"rm\s+(-[a-zA-Z]*\s+)*-?[a-zA-Z]*[rf]",  # rm -rf and friends
        r"mkfs(\.|\s)",
        r"dd\s+if=",
        r":\(\)\{.*\};:",  # fork bomb
        r"chmod\s+-R\s+777\s+/",
        r">\s*/dev/sd",
        r"\b(shutdown|reboot|halt)\b",
    ]
)

GIT_DESTRUCTIVE = r"(push\s+.*--force|push\s+.*-f\b|reset\s+--hard\s+origin|branch\s+-D\s)"

SECRET_EXFIL = (
    r"(curl|wget|nc|netcat).*(\$[A-Z_]*(KEY|TOKEN|SECRET|PASSWORD)|\.env|id_rsa|credentials)"
)


def default_policy() -> PermissionPolicy:
    """A conservative starting policy: read freely, write locally, never destroy."""
    return PermissionPolicy(
        rules=[
            Rule(
                tool="bash",
                argument_pattern=DESTRUCTIVE_SHELL,
                decision=Decision.DENY,
                reason="destructive filesystem or system command",
            ),
            Rule(
                tool="bash",
                argument_pattern=GIT_DESTRUCTIVE,
                decision=Decision.DENY,
                reason="destructive git operation",
            ),
            Rule(
                tool="bash",
                argument_pattern=SECRET_EXFIL,
                decision=Decision.DENY,
                reason="possible credential exfiltration",
            ),
            Rule(tool="read", decision=Decision.ALLOW),
            Rule(tool="glob", decision=Decision.ALLOW),
            Rule(tool="grep", decision=Decision.ALLOW),
            Rule(tool="write", decision=Decision.ALLOW),
            Rule(tool="edit", decision=Decision.ALLOW),
            Rule(tool="bash", decision=Decision.ALLOW),
        ],
        default=Decision.DENY,
    )


class PermissionDenied(Exception):
    def __init__(self, tool: str, reason: str) -> None:
        super().__init__(f"permission denied for tool {tool!r}: {reason}")
        self.tool = tool
        self.reason = reason


class PermissionPolicy(BaseModel):
    rules: list[Rule] = Field(default_factory=list)
    default: Decision = Decision.DENY

    def check(self, tool: str, arguments: dict[str, Any]) -> tuple[Decision, str]:
        for rule in self.rules:
            if rule.matches(tool, arguments):
                return rule.decision, rule.reason
        return self.default, "no matching rule"
