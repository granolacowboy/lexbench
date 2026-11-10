"""Fragment case grader: category and flag match."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

from graders.common import Verdict, clip

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _norm(value: Any) -> str:
    return re.sub(r"[\s-]+", "_", str(value).strip().lower())


def parse_object(response: str) -> dict[str, Any] | None:
    """The first JSON object in the response, with or without a code fence."""
    fenced = _FENCE.search(response)
    text = fenced.group(1) if fenced else response
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        obj = json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
                    return obj if isinstance(obj, dict) else None
        start = text.find("{", start + 1)
    return None


def grade_fragment(expected: Mapping[str, Any], response: str | None) -> Verdict:
    """expected: {"case_kind": "deadline", "category": str, "deadline_kind": str}
    or {"case_kind": "flags", "flags": [str, ...]}."""
    if response is None or not response.strip():
        return Verdict(False, "empty response")
    obj = parse_object(response)
    if obj is None:
        return Verdict(False, f"malformed response, no JSON object: {clip(response)!r}")
    if expected["case_kind"] == "deadline":
        if "category" not in obj or "kind" not in obj:
            return Verdict(False, "malformed response, category or kind missing")
        cat, kind = _norm(obj["category"]), _norm(obj["kind"])
        want_cat, want_kind = _norm(expected["category"]), _norm(expected["deadline_kind"])
        if cat != want_cat:
            return Verdict(False, f"category {cat!r}, expected {want_cat!r}")
        if kind != want_kind:
            return Verdict(False, f"kind {kind!r}, expected {want_kind!r}")
        return Verdict(True, "category and kind match")
    flags = obj.get("flags")
    if not isinstance(flags, list) or not all(isinstance(f, str) for f in flags):
        return Verdict(False, "malformed response, flags is not a list of strings")
    got = {_norm(f) for f in flags}
    want = {_norm(f) for f in expected["flags"]}
    if got == want:
        return Verdict(True, "flag set match")
    missing, extra = sorted(want - got), sorted(got - want)
    return Verdict(False, f"flags differ; missing {missing}, extra {extra}")
