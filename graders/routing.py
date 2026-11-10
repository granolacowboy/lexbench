"""Routing grader: command match."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from graders.common import Verdict, clip, first_line

_COMMAND = re.compile(r"/?([a-z][a-z0-9]*(?:-[a-z0-9]+)*)")


def grade_routing(expected: Mapping[str, Any], response: str | None) -> Verdict:
    """expected: {"command": str}. The first command-shaped token of the response counts."""
    if response is None or not response.strip():
        return Verdict(False, "empty response")
    line = first_line(response).lower().strip(" \t\"'`*")
    for prefix in ("command:", "answer:"):
        if line.startswith(prefix):
            line = line[len(prefix) :].strip(" \t\"'`*")
    match = _COMMAND.match(line)
    if not match:
        return Verdict(False, f"no command in response: {clip(response)!r}")
    got = match.group(1)
    gold = str(expected["command"]).lower()
    if got == gold:
        return Verdict(True, "command match")
    return Verdict(False, f"routed to {got!r}, expected {gold!r}")
