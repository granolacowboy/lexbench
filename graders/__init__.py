"""Deterministic graders, one function per family.

Each grader takes (expected, response) and returns a Verdict: whether the response is
correct and a short reason. expected is the record's "expected" mapping; response is the
model's text, or None when the provider returned no text. No grader calls a model.

grade_legalbench  label match over the whole response: after removing repeated answer cues
                  (one to four words and a colon, such as "Label:") from each line, the last
                  line that is exactly a label of the task's label space is the answer;
                  failing that, a label of at least two characters that opens the first
                  line and is followed by punctuation or the line end; see
                  graders/legalbench.py for the full rule and when it was settled
grade_fragment    category and deadline kind match for deadline cases; set equality of
                  attorney-review flags for intake cases; the last JSON object in the
                  response is the answer
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
