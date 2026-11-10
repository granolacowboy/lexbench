"""Deterministic graders, one function per family.

Each grader takes (expected, response) and returns a Verdict: whether the response is
correct and a short reason. expected is the record's "expected" mapping; response is the
model's text, or None when the provider returned no text. No grader calls a model.

grade_legalbench  normalised exact match against the task label; a response that begins
                  with exactly one label of the task's label space is read as that label
grade_fragment    category and deadline kind match for deadline cases; set equality of
                  attorney-review flags for intake cases; the response must be a JSON object
grade_routing     command match: the first command-shaped token, with an optional leading
                  slash, must equal the expected command
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from graders.common import Verdict
from graders.fragments import grade_fragment
from graders.legalbench import grade_legalbench
from graders.routing import grade_routing

Grader = Callable[[Mapping[str, Any], str | None], Verdict]

GRADERS: dict[str, Grader] = {
    "legalbench": grade_legalbench,
    "fragments": grade_fragment,
    "routing": grade_routing,
}

__all__ = ["GRADERS", "Grader", "Verdict", "grade_fragment", "grade_legalbench", "grade_routing"]
