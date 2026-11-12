"""Shared fixtures: a scratch repository root with real sources and a small LegalBench set."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

from lexbench.build import _files_entry, build
from lexbench.families import case_record
from lexbench.paths import Layout
from lexbench.records import read_json, write_json, write_jsonl

REPO = Path(__file__).resolve().parents[1]


def pytest_configure(config: pytest.Config) -> None:
    """Temporary test directories default to .lexbench-cache/pytest inside the repository,
    so that a test run writes nothing outside the workspace; --basetemp overrides."""
    if not config.option.basetemp:
        (REPO / ".lexbench-cache").mkdir(exist_ok=True)
        config.option.basetemp = str(REPO / ".lexbench-cache" / "pytest")


REGISTRY: dict[str, Any] = {
    "schema_version": 1,
    "limits": {"spend_cap_usd": 60.0, "max_requests_per_batch": 10000},
    "models": {
        "mock": {
            "provider": "mock",
            "model": "mock-oracle-1",
            "pricing": {"input_per_mtok": 0, "output_per_mtok": 0},
            "max_tokens": 256,
            "concurrency": 1,
            "batch": True,
            "options": {"mode": "oracle"},
        },
        "mock-sync": {
            "provider": "mock",
            "model": "mock-oracle-1",
            "pricing": {"input_per_mtok": 0, "output_per_mtok": 0},
            "max_tokens": 256,
            "concurrency": 2,
            "batch": False,
            "options": {"mode": "oracle"},
        },
        "mock-paid": {
            "provider": "mock",
            "model": "mock-oracle-1",
            "pricing": {"input_per_mtok": 3.0, "output_per_mtok": 15.0, "batch_discount": 0.5},
            "max_tokens": 256,
            "concurrency": 1,
            "batch": True,
            "options": {"mode": "oracle"},
        },
    },
}


def legalbench_fixture(layout: Layout) -> None:
    rows = []
    for i, (text, label) in enumerate(
        [
            ("A statement offered for its truth.", "Yes"),
            ("A question asked at trial.", "No"),
            ("A verbal act.", "No"),
        ]
    ):
        rows.append(
            case_record(
                id=f"lb-fixture-{i:04d}",
                family="legalbench",
                group="fixture_task",
                system="Answer with the label only.",
                prompt=f"Q: {text} Is there hearsay?\nA:",
                max_tokens=24,
                expected={"label": label, "labels": ["No", "Yes"]},
                meta={"reference": label, "choices": ["No", "Yes"]},
            )
        )
    path = layout.family_dir("legalbench") / "fixture_task.jsonl"
    write_jsonl(path, rows)
    manifest = read_json(layout.manifest, default=None) or {"schema_version": 1, "families": {}}
    entry = _files_entry(layout, [path])
    entry["tasks"] = {"fixture_task": "rule-application"}
    manifest["families"]["legalbench"] = entry
    write_json(layout.manifest, manifest)


@pytest.fixture()
def layout(tmp_path: Path) -> Layout:
    root = tmp_path / "repo"
    shutil.copytree(REPO / "sources", root / "sources")
    (root / "models.yaml").write_text(yaml.safe_dump(REGISTRY), encoding="utf-8")
    (root / "README.md").write_text(
        "# t\n<!-- results:start -->\n<!-- results:end -->\n", encoding="utf-8"
    )
    lay = Layout(root)
    build(lay, ["fragments", "routing"])
    legalbench_fixture(lay)
    return lay
