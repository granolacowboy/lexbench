"""Routing grader: command match."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from typing import Any

from graders.common import Verdict, clip, first_line

COMMAND_NAME = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*"
_COMMAND = re.compile(rf"/?({COMMAND_NAME})")
_NAME = re.compile(COMMAND_NAME)


def check_command_names(names: Iterable[str]) -> None:
    """Refuse a command name that grade_routing cannot match.

    The grader reads the first command-shaped token of a response (lower-case letters and
    digits, in hyphen-separated parts, starting with a letter). A gold command of another
    shape (an underscore, a plugin:command namespace, a dot or a leading digit) could never
    be matched, and every case for it would be graded wrong.
    """
    bad = sorted({str(n) for n in names if not _NAME.fullmatch(str(n).lower())})
    if bad:
        shown = ", ".join(repr(n) for n in bad[:5])
        raise ValueError(
            f"routing: command name {shown} cannot be matched by the routing grader "
            f"(pattern {COMMAND_NAME})"
        )


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
