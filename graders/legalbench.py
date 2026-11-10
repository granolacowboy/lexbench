"""LegalBench grader: label match over the whole response.

The rule (settled 2026-11-10 in run FIX-LEXBENCH-1, before the rerun batches were
submitted; it replaces the two-line rule of the first results):

1. Every non-empty line of the response is read. From each line, repeated answer cues (one
   to four words and a colon, such as "A:", "Label:" or "Governed by:") and edge
   punctuation are removed, and the case is folded.
2. The answer is the last line that is then exactly a label of the task's label space. A
   model that explains its reasoning states its answer at the end, so the last label line
   is taken; this is the rule the fragment grader applies to JSON objects.
3. When no line is exactly a label, the first line is read for a leading label: a label of
   at least two characters, at the start of the line, followed by punctuation or the end
   of the line ("Yes, because ..."). A single-letter label is never read from a prefix, and
   a label followed by a further word ("Yes or no: ...") is not read.
4. Otherwise the response has no label and counts as incorrect (a format failure).
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from graders.common import EDGE, Verdict, clip, first_line, normalise_line

# A leading label must be followed by one of these, or by the end of the line.
_AFTER_LABEL = r"(?:[,.;:!?)]|$)"


def _label_lines(response: str) -> list[str]:
    return [normalise_line(ln) for ln in response.splitlines() if ln.strip()]


def grade_legalbench(expected: Mapping[str, Any], response: str | None) -> Verdict:
    """expected: {"label": str, "labels": [str, ...]}."""
    if response is None or not response.strip():
        return Verdict(False, "empty response")
    gold = normalise_line(str(expected["label"]))
    labels = {normalise_line(str(x)) for x in expected.get("labels", [])} | {gold}
    found = [got for got in _label_lines(response) if got in labels]
    if found:
        got = found[-1]
        if got == gold:
            return Verdict(True, "exact match" if len(found) == 1 else "last label line")
        return Verdict(False, f"predicted {got!r}, expected {gold!r}")
    raw = re.sub(r"\s+", " ", first_line(response).strip(EDGE)).lower()
    for text in (raw, normalise_line(first_line(response))):
        prefixed = [
            lab
            for lab in labels
            if len(lab) >= 2 and re.match(rf"{re.escape(lab)}{_AFTER_LABEL}", text)
        ]
        if prefixed:
            # The longest label wins when one label is a prefix of another.
            pick = max(prefixed, key=lambda lab: (len(lab), lab))
            if pick == gold:
                return Verdict(True, "label read from response prefix")
            return Verdict(False, f"predicted {pick!r} (prefix), expected {gold!r}")
    return Verdict(False, f"no label in response: {clip(response)!r}")
