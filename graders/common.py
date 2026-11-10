"""Shared verdict type and text normalisation."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PREFIX = re.compile(r"^(?:a|answer|label|response|output)\s*[:\-]\s*", re.IGNORECASE)
_EDGE = " \t\r\n\"'`*_.,;:!?()[]{}<>"


@dataclass(frozen=True)
class Verdict:
    correct: bool
    reason: str


def first_line(text: str) -> str:
    for line in text.strip().splitlines():
        if line.strip():
            return line.strip()
    return ""


def normalise(text: str) -> str:
    """Lower case, first non-empty line, answer prefixes and edge punctuation removed."""
    line = first_line(text)
    previous = None
    while previous != line:
        previous = line
        line = _PREFIX.sub("", line.strip(_EDGE))
    return re.sub(r"\s+", " ", line.strip(_EDGE)).lower()


def clip(text: str | None, limit: int = 60) -> str:
    if text is None:
        return ""
    flat = re.sub(r"\s+", " ", text).strip()
    return flat if len(flat) <= limit else flat[: limit - 3] + "..."
