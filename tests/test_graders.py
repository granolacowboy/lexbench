"""Graders on fixtures, including malformed responses."""

from __future__ import annotations

import pytest

from graders import grade_fragment, grade_legalbench, grade_routing
from graders.common import normalise

YESNO = {"label": "Yes", "labels": ["No", "Yes"]}
SECTIONS = {
    "label": "Procedural History",
    "labels": ["Analysis", "Facts", "Procedural History", "Rule"],
}


@pytest.mark.parametrize(
    "response, ok",
    [
        ("Yes", True),
        (" yes.\n", True),
        ("A: Yes", True),
        ("**Yes**", True),
        ("Yes, because the statement is offered for its truth.", True),
        ("No", False),
        ("", False),
        (None, False),
        ("Maybe", False),
        ("Yesterday", False),
    ],
)
def test_legalbench_yes_no(response: str | None, ok: bool) -> None:
    assert grade_legalbench(YESNO, response).correct is ok


def test_legalbench_multiword_label_and_reason() -> None:
    assert grade_legalbench(SECTIONS, "Label: Procedural History").correct
    verdict = grade_legalbench(SECTIONS, "Facts")
    assert not verdict.correct and "predicted 'facts'" in verdict.reason


def test_normalise() -> None:
    assert normalise("\n\nAnswer: Common Law.\nmore") == "common law"


DEADLINE = {"case_kind": "deadline", "category": "answer_deadline", "deadline_kind": "statutory"}
FLAGS = {"case_kind": "flags", "flags": ["conflict_match", "outside_jurisdiction"]}
NONE = {"case_kind": "flags", "flags": []}


@pytest.mark.parametrize(
    "response, ok",
    [
        ('{"category": "answer_deadline", "kind": "statutory"}', True),
        ('```json\n{"category": "answer_deadline", "kind": "Statutory"}\n```', True),
        ('Here: {"category": "answer_deadline", "kind": "firm_set"}', False),
        ('{"category": "appeal_window", "kind": "statutory"}', False),
        ('{"category": "answer_deadline"}', False),
        ('{"category": "answer_deadline", "kind": ', False),
        ("answer_deadline, statutory", False),
        ("", False),
        (None, False),
    ],
)
def test_fragment_deadline(response: str | None, ok: bool) -> None:
    assert grade_fragment(DEADLINE, response).correct is ok


def test_fragment_firm_set_spelling() -> None:
    exp = {"case_kind": "deadline", "category": "annual_meeting", "deadline_kind": "firm_set"}
    assert grade_fragment(exp, '{"category": "annual_meeting", "kind": "firm-set"}').correct


@pytest.mark.parametrize(
    "response, ok",
    [
        ('{"flags": ["outside_jurisdiction", "conflict_match"]}', True),
        ('{"flags": ["conflict_match"]}', False),
        ('{"flags": ["conflict_match", "outside_jurisdiction", "possible_conflict"]}', False),
        ('{"flags": "conflict_match"}', False),
        ('{"flag": []}', False),
        ("[]", False),
    ],
)
def test_fragment_flags(response: str, ok: bool) -> None:
    assert grade_fragment(FLAGS, response).correct is ok


def test_fragment_no_flags() -> None:
    assert grade_fragment(NONE, '{"flags": []}').correct
    assert not grade_fragment(NONE, '{"flags": ["conflict_match"]}').correct


@pytest.mark.parametrize(
    "response, ok",
    [
        ("brief", True),
        ("/brief", True),
        ("`brief`", True),
        ("Command: brief", True),
        ("brief\nBecause it lists due items.", True),
        ("dates", False),
        ("I would use the brief command", False),
        ("", False),
        (None, False),
        ("???", False),
    ],
)
def test_routing(response: str | None, ok: bool) -> None:
    assert grade_routing({"command": "brief"}, response).correct is ok


def test_routing_hyphenated() -> None:
    assert grade_routing({"command": "before-i-paste"}, "/before-i-paste").correct
    assert not grade_routing({"command": "before-i-paste"}, "before").correct
