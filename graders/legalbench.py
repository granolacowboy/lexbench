"""LegalBench grader: normalised exact match for label tasks."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from graders.common import Verdict, clip, normalise


def grade_legalbench(expected: Mapping[str, Any], response: str | None) -> Verdict:
    """expected: {"label": str, "labels": [str, ...]}."""
    if response is None or not response.strip():
        return Verdict(False, "empty response")
    gold = normalise(str(expected["label"]))
    labels = {normalise(str(x)) for x in expected.get("labels", [])} | {gold}
    got = normalise(response)
    if got == gold:
        return Verdict(True, "exact match")
    if got in labels:
        return Verdict(False, f"predicted {got!r}, expected {gold!r}")
    prefixed = [lab for lab in labels if re.match(rf"{re.escape(lab)}(?:\W|$)", got)]
    if prefixed:
        # The longest label wins when one label is a prefix of another.
        pick = max(prefixed, key=lambda lab: (len(lab), lab))
        if pick == gold:
            return Verdict(True, "label read from response prefix")
        return Verdict(False, f"predicted {pick!r} (prefix), expected {gold!r}")
    return Verdict(False, f"no label in response: {clip(response)!r}")
