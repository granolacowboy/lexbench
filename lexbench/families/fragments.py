"""Fragment family: synthetic intake and deadline cases generated from each pack fragment.

Inputs are the imported fragment fields alone (intake questions, deadline categories with
kind statutory or firm_set, attorney-review flags) and the templates in
sources/fragments/templates.yaml. Output is deterministic for a given seed: names, dates
and settings are drawn from random.Random seeded with the seed and the pack name.

Per pack: two deadline cases per category (expected: category id and kind), two cases per
flag with the flag's rule met (expected: that flag), one case with two flags met, two cases
with no rule met (expected: no flags), padded with further deadline cases to at least
MIN_CASES. Sensitive intake questions are never shown.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml

from lexbench.families import case_record

FAMILY = "fragments"
SEED = 20261110
MIN_CASES = 12
MAX_TOKENS = 600
SYSTEM = (
    "You apply a practice-area fragment to synthetic case data for a law firm. "
    "Answer with one JSON object and nothing else."
)
PREFIX = "mhsb-pack-"


class _Draw:
    """All random values for one case, drawn in a fixed order."""

    def __init__(self, rng: random.Random, names: dict[str, list[str]]) -> None:
        self.today = date(2026, 1, 5) + timedelta(days=rng.randint(0, 300))
        people = rng.sample([f"{f} {last}" for f in names["first"] for last in names["last"]], 6)
        states = rng.sample(names["states"], 2)
        t = self.today

        def back(lo: int, hi: int) -> str:
            return (t - timedelta(days=rng.randint(lo, hi))).isoformat()

        def ahead(lo: int, hi: int) -> str:
            return (t + timedelta(days=rng.randint(lo, hi))).isoformat()

        self.values: dict[str, str] = {
            "client": people[0],
            "other": people[1],
            "lawyer": people[2],
            "conflict": people[3],
            "company": rng.choice(names["company"]),
            "state": states[0],
            "other_state": states[1],
            "d_past": back(5, 60),
            "d_future": ahead(10, 90),
            "d_recent": back(14, 180),
            "d_old": back(575, 900),
            "d_150": back(160, 300),
            "d_near": ahead(1, 6),
            "d_far": ahead(15, 40),
            "d_5": back(5, 20),
            "d_30": back(40, 120),
            "year_recent": str(t.year - rng.randint(2, 6)),
            "n_small": str(rng.randint(3, 12)),
            "n_large": str(rng.randint(40, 400)),
        }
        self.conflict_list = [people[3], people[4], people[5]]
        rng.shuffle(self.conflict_list)
        self.rng = rng


def _deadline_case(
    pack: dict[str, Any], cat: dict[str, Any], template: str, d: _Draw
) -> tuple[str, dict[str, Any], str]:
    lines = "\n".join(
        f"- {c['id']} ({c['kind']}): {c['name']}" for c in pack["deadline_categories"]
    )
    event = template.format(**d.values)
    prompt = (
        f"Practice area: {pack['practice_area'].replace('_', ' ')}\n"
        f"Deadline categories defined by the fragment (id, kind, name):\n{lines}\n\n"
        f"Today's date: {d.today.isoformat()}\n"
        f"Matter for {d.values['client']}.\nEvent: {event}\n\n"
        "Which deadline category does this event belong to, and what kind is that category "
        "under the fragment?\n"
        'Answer with a JSON object: {"category": "<category id>", "kind": "statutory" or '
        '"firm_set"}'
    )
    expected = {"case_kind": "deadline", "category": cat["id"], "deadline_kind": cat["kind"]}
    reference = json.dumps({"category": cat["id"], "kind": cat["kind"]})
    return prompt, expected, reference


def _flags_case(
    pack: dict[str, Any], short: str, raised: list[str], tpl: dict[str, Any], d: _Draw, variant: int
) -> tuple[str, dict[str, Any], str]:
    flags: list[str] = pack["attorney_review_flags"]
    rules = "\n".join(f"- {f}: {tpl['flags'][f]['rule']}" for f in flags)
    values = dict(d.values)
    settings = [f"Practice state: {values['state']}."]
    if {"conflict_match", "possible_conflict"} & set(flags):
        settings.append("Conflict list: " + "; ".join(d.conflict_list) + ".")
    if "outside_case_types" in flags:
        types = tpl["case_types"][short]
        values["accepted_type"] = d.rng.choice(types["accepted"])
        values["rejected_type"] = d.rng.choice(types["rejected"])
        settings.append("Accepted matter types: " + ", ".join(types["accepted"]) + ".")
    facts = []
    for f in flags:
        spec = tpl["flags"][f]
        text = spec["signal"][variant % len(spec["signal"])] if f in raised else spec["neutral"]
        facts.append("- " + text.format(**values))
    questions = "; ".join(q["prompt"] for q in pack["intake_questions"] if not q["sensitive"])
    prompt = (
        f"Practice area: {pack['practice_area'].replace('_', ' ')}\n"
        f"Firm settings: {' '.join(settings)}\n"
        f"Attorney-review flags defined by the fragment, with the rule for each:\n{rules}\n"
        f"Intake questions defined by the fragment (sensitive questions omitted): {questions}.\n\n"
        f"Today's date: {d.today.isoformat()}\n"
        f"Intake record for {values['client']}:\n" + "\n".join(facts) + "\n\n"
        "Which attorney-review flags does this record raise? A flag never declines a matter; "
        "list every flag whose rule is met and no other.\n"
        'Answer with a JSON object: {"flags": ["<flag id>", ...]}, with an empty list when '
        "no rule is met."
    )
    want = sorted(raised)
    return prompt, {"case_kind": "flags", "flags": want}, json.dumps({"flags": want})


def build_pack(pack: dict[str, Any], tpl: dict[str, Any], seed: int = SEED) -> list[dict[str, Any]]:
    name: str = pack["pack"]
    short = name.removeprefix(PREFIX)
    rng = random.Random(f"{seed}:{name}")
    plan: list[tuple[str, Any, int]] = []
    for cat in pack["deadline_categories"]:
        plan += [("deadline", cat, 0), ("deadline", cat, 1)]
    flags: list[str] = pack["attorney_review_flags"]
    for f in flags:
        plan += [("flags", [f], 0), ("flags", [f], 1)]
    if len(flags) >= 2:
        plan.append(("flags", sorted(rng.sample(flags, 2)), 0))
    plan += [("flags", [], 0), ("flags", [], 1)]
    extra = 0
    while len(plan) < MIN_CASES:
        cats = pack["deadline_categories"]
        plan.append(("deadline", cats[extra % len(cats)], extra))
        extra += 1

    rows: list[dict[str, Any]] = []
    for i, (kind, item, variant) in enumerate(plan, start=1):
        d = _Draw(rng, tpl["names"])
        if kind == "deadline":
            key = f"{short}/{item['id']}"
            templates = tpl["deadline_scenarios"][key]
            template = templates[variant % len(templates)]
            prompt, expected, ref = _deadline_case(pack, item, template, d)
        else:
            prompt, expected, ref = _flags_case(pack, short, item, tpl, d, variant)
        rows.append(
            case_record(
                id=f"fr-{short}-{i:03d}",
                family=FAMILY,
                group=name,
                system=SYSTEM,
                prompt=prompt,
                max_tokens=MAX_TOKENS,
                expected=expected,
                meta={"reference": ref, "choices": [ref]},
            )
        )
    return rows


def build(sources: Path, seed: int = SEED) -> dict[str, list[dict[str, Any]]]:
    tpl = yaml.safe_load((sources / "fragments" / "templates.yaml").read_text(encoding="utf-8"))
    out: dict[str, list[dict[str, Any]]] = {}
    for path in sorted((sources / "mhsb" / "fragments").glob("*.yaml")):
        pack = yaml.safe_load(path.read_text(encoding="utf-8"))
        out[pack["pack"]] = build_pack(pack, tpl, seed)
    if len(out) != 12:
        raise ValueError(f"fragments: expected twelve packs, found {len(out)}")
    return out
