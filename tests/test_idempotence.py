"""`run` is idempotent against a recorded batch."""

from __future__ import annotations

import pytest

from lexbench.build import family_sha
from lexbench.estimate import estimate
from lexbench.paths import Layout
from lexbench.providers.anthropic_provider import AnthropicProvider
from lexbench.records import read_json, write_json
from lexbench.registry import load_registry
from lexbench.runner import run


def test_second_run_submits_nothing(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock"], fetch_prices=False)
    first = run(layout, reg, "fragments", "mock", log=lambda _s: None)
    second = run(layout, reg, "fragments", "mock", log=lambda _s: None)
    assert first == second
    assert len(read_json(layout.batches)["batches"]) == 1


def test_recorded_batch_is_not_resubmitted(layout: Layout, monkeypatch: pytest.MonkeyPatch) -> None:
    """A batch recorded for a paid entry blocks a new submission without any provider call."""
    (layout.models_yaml).write_text(
        layout.models_yaml.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    fingerprint = load_registry(layout.models_yaml).get("mock-paid").fingerprint()
    raw = read_json(layout.batches, default=None) or {"schema_version": 1, "batches": []}
    raw["batches"].append(
        {
            "batch_id": "msgbatch_recorded",
            "family": "routing",
            "model": "mock-paid",
            "provider": "mock",
            "provider_model": "mock-oracle-1",
            "request_count": 1,
            "estimated_usd": 0.01,
            "data_sha256": family_sha(layout, "routing"),
            "config_sha256": fingerprint,
            "chunk": "1/1",
            "submitted_at": "2026-11-10T00:00:00Z",
            "status": "in_progress",
            "counts": {},
            "ended_at": None,
        }
    )
    write_json(layout.batches, raw)

    def forbidden(*_a: object, **_k: object) -> str:
        raise AssertionError("submit_batch must not be called")

    monkeypatch.setattr(AnthropicProvider, "submit_batch", forbidden)
    monkeypatch.setattr("lexbench.providers.mock.MockProvider.submit_batch", forbidden)
    reg = load_registry(layout.models_yaml)
    ids = run(layout, reg, "routing", "mock-paid", log=lambda _s: None)
    assert ids == ["msgbatch_recorded"]
    assert len(read_json(layout.batches)["batches"]) == 1


def test_changed_data_allows_a_new_submission(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    raw = {
        "schema_version": 1,
        "batches": [
            {
                "batch_id": "old",
                "family": "routing",
                "model": "mock",
                "provider": "mock",
                "provider_model": "m",
                "request_count": 1,
                "estimated_usd": 0.0,
                "data_sha256": "f" * 64,
                "chunk": "1/1",
                "submitted_at": "2026-01-01T00:00:00Z",
                "status": "ended",
                "counts": {},
                "ended_at": None,
            }
        ],
    }
    write_json(layout.batches, raw)
    estimate(layout, reg, ["mock"], fetch_prices=False)
    ids = run(layout, reg, "routing", "mock", log=lambda _s: None)
    assert ids != ["old"]


def test_changed_settings_allow_a_new_submission_and_keep_spend(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-paid"], fetch_prices=False)
    first = run(layout, reg, "routing", "mock-paid", log=lambda _s: None)
    spent = read_json(layout.batches)["batches"][0]["estimated_usd"]
    text = layout.models_yaml.read_text(encoding="utf-8")
    marker = "  mock-paid:\n"
    assert marker in text
    text = text.replace(marker, marker + "    reasoning_tokens: 64\n")
    layout.models_yaml.write_text(text, encoding="utf-8")
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-paid"], fetch_prices=False)
    second = run(layout, reg, "routing", "mock-paid", log=lambda _s: None)
    assert second != first
    batches = read_json(layout.batches)["batches"]
    assert len(batches) == 2
    assert batches[1]["estimated_usd"] > spent  # the reasoning room is priced
