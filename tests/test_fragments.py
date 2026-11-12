"""The fragment generator is deterministic and its expected answers follow the fragment."""

from __future__ import annotations

import json

import yaml

from lexbench.families import fragments, routing
from tests.conftest import REPO

SOURCES = REPO / "sources"


def test_generator_is_deterministic() -> None:
    first = fragments.build(SOURCES, seed=fragments.SEED)
    second = fragments.build(SOURCES, seed=fragments.SEED)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    other = fragments.build(SOURCES, seed=fragments.SEED + 1)
    assert json.dumps(first, sort_keys=True) != json.dumps(other, sort_keys=True)


def test_committed_data_matches_the_generator() -> None:
    for pack, rows in fragments.build(SOURCES).items():
        path = REPO / "data" / "fragments" / f"{pack}.jsonl"
        committed = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        assert committed == rows, pack


def test_expected_answers_follow_the_fragment() -> None:
    for pack, rows in fragments.build(SOURCES).items():
        frag = yaml.safe_load((SOURCES / "mhsb" / "fragments" / f"{pack}.yaml").read_text())
        kinds = {c["id"]: c["kind"] for c in frag["deadline_categories"]}
        flags = set(frag["attorney_review_flags"])
        assert len(rows) >= 10, pack
        assert len({r["id"] for r in rows}) == len(rows)
        seen_cats = set()
        for r in rows:
            exp = r["expected"]
            if exp["case_kind"] == "deadline":
                assert kinds[exp["category"]] == exp["deadline_kind"]
                assert exp["deadline_kind"] in {"statutory", "firm_set"}
                seen_cats.add(exp["category"])
            else:
                assert set(exp["flags"]) <= flags
        assert seen_cats == set(kinds), pack
        sensitive = [q["prompt"] for q in frag["intake_questions"] if q["sensitive"]]
        for r in rows:
            assert not any(s in r["prompt"] for s in sensitive)


def test_routing_has_two_paraphrases_per_command() -> None:
    rows = routing.build(SOURCES)["cases"]
    per: dict[str, int] = {}
    for r in rows:
        if r["group"] == "paraphrase":
            per[r["expected"]["command"]] = per.get(r["expected"]["command"], 0) + 1
    commands = yaml.safe_load((SOURCES / "routing" / "commands.yaml").read_text())["commands"]
    assert set(per) == set(commands)
    assert min(per.values()) >= 2
