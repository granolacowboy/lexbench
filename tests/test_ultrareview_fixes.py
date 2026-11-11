"""Regression tests for the ultrareview findings L1 to L10 on pull request #1.

Each test was written before its fix and run against head e235f92; state/RUNLOG.md records
which failed there. Every test runs through the mock provider or without a network call.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from lexbench import runner
from lexbench.build import family_sha
from lexbench.estimate import estimate
from lexbench.paths import Layout
from lexbench.providers import ProviderError
from lexbench.providers.anthropic_provider import AnthropicProvider
from lexbench.providers.mock import MockProvider
from lexbench.providers.openai_compatible import OpenAICompatibleProvider
from lexbench.records import Request, read_json, read_jsonl, write_json
from lexbench.registry import load_registry, parse_registry
from tests.conftest import REPO


def QUIET(_s: str) -> None:
    return None


def _edit_registry(
    layout: Layout,
    models: dict[str, dict[str, Any]] | None = None,
    limits: dict[str, Any] | None = None,
) -> None:
    raw = yaml.safe_load(layout.models_yaml.read_text(encoding="utf-8"))
    for name, extra in (models or {}).items():
        raw["models"][name].update(extra)
    raw["limits"].update(limits or {})
    layout.models_yaml.write_text(yaml.safe_dump(raw), encoding="utf-8")


def _entry(**body: Any) -> Any:
    base: dict[str, Any] = {
        "provider": "mock",
        "model": "m",
        "pricing": {"input_per_mtok": 0, "output_per_mtok": 0},
        "max_tokens": 256,
        "concurrency": 1,
        "batch": False,
    }
    base.update(body)
    return parse_registry({"schema_version": 1, "models": {"e": base}}).get("e")


# L1: a family split into chunks is completed by a rerun after a failed chunk.


def test_l1_failed_middle_chunk_is_resubmitted_on_rerun(
    layout: Layout, monkeypatch: pytest.MonkeyPatch
) -> None:
    _edit_registry(layout, limits={"max_requests_per_batch": 100})
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock"], fetch_prices=False)
    real = MockProvider.submit_batch
    calls: list[int] = []

    def second_fails(self: MockProvider, requests: Any) -> str:
        calls.append(len(requests))
        recorded = read_json(layout.batches)["batches"][-1]
        assert recorded["status"] == "pending"
        assert (recorded["chunk_index"], recorded["chunk_total"]) == (len(calls), 3)
        if len(calls) == 2:
            raise ProviderError("simulated refusal of the second chunk")
        return real(self, requests)

    monkeypatch.setattr(MockProvider, "submit_batch", second_fails)
    with pytest.raises(ProviderError):
        runner.run(layout, reg, "routing", "mock", log=QUIET)
    batches = read_json(layout.batches)["batches"]
    assert [(b["chunk_index"], b["status"]) for b in batches] == [(1, "in_progress"), (2, "failed")]

    monkeypatch.setattr(MockProvider, "submit_batch", real)
    resubmitted = runner.run(layout, reg, "routing", "mock", log=QUIET)
    assert len(resubmitted) == 2
    live = [b for b in read_json(layout.batches)["batches"] if b["status"] != "failed"]
    assert sorted(b["chunk_index"] for b in live) == [1, 2, 3]
    assert sum(b["request_count"] for b in live) == 271

    said: list[str] = []
    runner.run(layout, reg, "routing", "mock", log=said.append)
    assert "already submitted" in said[-1] and "nothing to do" in said[-1]
    assert len(read_json(layout.batches)["batches"]) == 4

    runner.poll(layout, reg, log=QUIET)
    rows = read_jsonl(layout.graded_path("routing", "mock"))
    assert len(rows) == 271 and all(r["correct"] for r in rows)


def test_l1_no_nothing_to_do_while_a_chunk_is_unrecorded(layout: Layout) -> None:
    """A family with one of three chunks recorded is not reported as complete."""
    _edit_registry(layout, limits={"max_requests_per_batch": 100})
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock"], fetch_prices=False)
    write_json(
        layout.batches,
        {
            "schema_version": 1,
            "batches": [
                {
                    "batch_id": "mockbatch_recorded",
                    "submission_id": "sub_recorded_1",
                    "family": "routing",
                    "model": "mock",
                    "provider": "mock",
                    "provider_model": "mock-oracle-1",
                    "request_count": 100,
                    "estimated_usd": 0.0,
                    "data_sha256": family_sha(layout, "routing"),
                    "config_sha256": reg.get("mock").fingerprint("routing"),
                    "chunk": "1/3",
                    "submitted_at": "2026-11-11T00:00:00Z",
                    "status": "in_progress",
                    "counts": {},
                    "ended_at": None,
                }
            ],
        },
    )
    said: list[str] = []
    ids = runner.run(layout, reg, "routing", "mock", log=said.append)
    assert len(ids) == 2
    assert not any("nothing to do" in s for s in said)


# L2: an estimate priced with the batch discount is refused for a synchronous entry.


def test_l2_batch_priced_estimate_refused_after_switch_to_synchronous(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-paid"], fetch_prices=False)
    _edit_registry(layout, {"mock-paid": {"batch": False}})
    reg = load_registry(layout.models_yaml)
    with pytest.raises(runner.CapExceeded, match="batch"):
        runner.run(layout, reg, "routing", "mock-paid", log=QUIET)
    assert read_json(layout.runs) is None


def test_l2_recorded_estimate_of_record_remains_accepted() -> None:
    """The estimate of record (results/estimate.json) passes the extended comparison for
    every Claude entry and family, so the change orphans no recorded estimate."""
    reg = load_registry(REPO / "models.yaml")
    est = read_json(REPO / "results" / "estimate.json")
    for name in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"):
        for family, recorded in est["entries"][name].items():
            runner.check_estimate_entry(recorded, reg.get(name), family, name)


# L3: params cannot raise the output bound or add an unpriced thinking budget.


@pytest.mark.parametrize(
    "params",
    [
        {"max_tokens": 100000},
        {"thinking": {"type": "enabled", "budget_tokens": 32000}},
    ],
)
def test_l3_anthropic_params_cannot_exceed_the_priced_bound(params: dict[str, Any]) -> None:
    entry = _entry(provider="anthropic", options={"params": params})
    provider = AnthropicProvider(entry, Path("unused"))
    req = Request("c1", "s", "p", 24)
    with pytest.raises(ProviderError, match="output bound"):
        provider._params(req)
    with pytest.raises(ProviderError, match="output bound"):
        provider.estimate([req])


@pytest.mark.parametrize("key", ["max_tokens", "max_completion_tokens"])
def test_l3_openai_params_cannot_exceed_the_priced_bound(key: str) -> None:
    entry = _entry(
        provider="openai_compatible",
        endpoint="http://127.0.0.1:9/v1",
        options={"params": {key: 100000}},
    )
    provider = OpenAICompatibleProvider(entry, Path("unused"))
    req = Request("c1", "s", "p", 24)
    with pytest.raises(ProviderError, match="output bound"):
        provider._body(req)
    with pytest.raises(ProviderError, match="output bound"):
        provider.estimate([req])


def test_l3_family_settings_params_are_checked_too() -> None:
    entry = _entry(
        provider="anthropic",
        family_settings={"routing": {"params": {"max_tokens": 5000}}},
    ).for_family("routing")
    with pytest.raises(ProviderError, match="output bound"):
        AnthropicProvider(entry, Path("unused"))._params(Request("c1", "s", "p", 20))


def test_l3_params_within_the_bound_and_the_registry_of_record_pass() -> None:
    entry = _entry(provider="anthropic", options={"params": {"max_tokens": 16}})
    assert (
        AnthropicProvider(entry, Path("unused"))._params(Request("c", "s", "p", 24))["max_tokens"]
        == 16
    )
    reg = load_registry(REPO / "models.yaml")
    for name in ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"):
        for family, bound in (("legalbench", 24), ("fragments", 600), ("routing", 20)):
            provider = AnthropicProvider(reg.get(name).for_family(family), Path("unused"))
            provider._params(Request("c", "s", "p", bound))
