"""Shared verdict type and text normalisation."""

from __future__ import annotations

import re
from dataclasses import dataclass

# An answer cue repeated at the start of a response: the LegalBench prompts end with cues
# such as "A:", "Label:", "Answer:", "FINAL ANSWER:" or "Governed by:". Any cue of one to
# four words followed by a colon is removed.
_PREFIX = re.compile(r"^(?:[a-z]+(?: [a-z]+){0,3})\s*:\s*", re.IGNORECASE)
EDGE = " \t\r\n\"'`*_.,;:!?()[]{}<>"


@dataclass(frozen=True)
class Verdict:
    correct: bool
    reason: str


def first_line(text: str) -> str:
    for line in text.strip().splitlines():
        if line.strip():
            return line.strip()
    return ""


def _strip_cues(line: str) -> str:
    previous = None
    while previous != line:
        previous = line
        line = _PREFIX.sub("", line.strip(EDGE.replace(":", "")))
    return re.sub(r"\s+", " ", line.strip(EDGE)).lower()


def normalise_line(line: str) -> str:
    """One line with answer cues and edge punctuation removed, in lower case."""
    return _strip_cues(line)


def normalise(text: str) -> str:
    """Lower case, first non-empty line, answer cues and edge punctuation removed.

    When the first line holds only an answer cue (for example "A:"), the next non-empty
    line is read instead.
    """
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    for line in lines[:2]:
        got = _strip_cues(line)
        if got:
            return got
    return ""


def clip(text: str | None, limit: int = 60) -> str:
    if text is None:
        return ""
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."
