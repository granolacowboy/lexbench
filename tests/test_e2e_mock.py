"""End-to-end run of every family through the mock provider, batch and synchronous."""

from __future__ import annotations

import pytest

from lexbench import cli
from lexbench.paths import FAMILIES, Layout
from lexbench.records import read_json, read_jsonl


@pytest.mark.parametrize("model", ["mock", "mock-sync"])
def test_every_family_end_to_end(layout: Layout, model: str) -> None:
    root = ["--root", str(layout.root)]
    assert cli.main([*root, "estimate", "--no-fetch", "--model", model]) == 0
    for family in FAMILIES:
        assert cli.main([*root, "run", "--family", family, "--model", model]) == 0
    assert cli.main([*root, "poll"]) == 0
    assert cli.main([*root, "grade", "--model", model]) == 0
    assert cli.main([*root, "report"]) == 0
    for family in FAMILIES:
        rows = read_jsonl(layout.graded_path(family, model))
        assert rows and all(r["correct"] for r in rows), family
    summary = read_json(layout.summary)
    assert summary["models"] == [model]
    assert summary["families"]["routing"]["overall"][model]["passes"] is True
    assert summary["families"]["fragments"]["overall"][model]["accuracy"] == 1.0
    readme = (layout.root / "README.md").read_text(encoding="utf-8")
    assert f"| Family | Task or group | n | {model} |" in readme


def test_hash_mode_is_deterministic_and_graded(layout: Layout) -> None:
    text = layout.models_yaml.read_text(encoding="utf-8").replace("mode: oracle", "mode: hash", 1)
    layout.models_yaml.write_text(text, encoding="utf-8")
    root = ["--root", str(layout.root)]
    assert cli.main([*root, "estimate", "--no-fetch", "--model", "mock"]) == 0
    assert cli.main([*root, "run", "--family", "routing", "--model", "mock"]) == 0
    assert cli.main([*root, "poll"]) == 0
    first = [r["response"] for r in read_jsonl(layout.graded_path("routing", "mock"))]
    assert cli.main([*root, "grade", "--model", "mock", "--family", "routing"]) == 0
    second = [r["response"] for r in read_jsonl(layout.graded_path("routing", "mock"))]
    assert first == second
