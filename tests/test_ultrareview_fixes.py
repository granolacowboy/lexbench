"""Regression tests for the ultrareview findings L1 to L10 on pull request #1.

Each test was written before its fix and run against head e235f92; state/RUNLOG.md records
which failed there. Every test runs through the mock provider or without a network call.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
import yaml

from lexbench import runner
from lexbench.build import family_sha
from lexbench.estimate import estimate
from lexbench.paths import Layout
from lexbench.providers import ProviderError, make_provider
from lexbench.providers.anthropic_provider import AnthropicProvider
from lexbench.providers.mock import MockProvider
from lexbench.providers.openai_compatible import OpenAICompatibleProvider
from lexbench.records import Request, read_json, read_jsonl, utc_now, write_json
from lexbench.registry import RegistryError, load_registry, parse_registry
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


# L4: billed attempts are bounded by the schema and priced by the estimate.


@pytest.mark.parametrize("retries", [4, 10, -1, "3"])
def test_l4_retries_have_a_schema_ceiling(retries: Any) -> None:
    with pytest.raises(RegistryError, match="retries"):
        _entry(options={"retries": retries})


def test_l4_anthropic_client_max_retries_matches_the_bound(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LEXBENCH_TEST_CREDENTIAL", "placeholder-not-a-credential")
    default = _entry(provider="anthropic", auth="LEXBENCH_TEST_CREDENTIAL")
    assert AnthropicProvider(default, Path("unused"))._client().max_retries == 3
    one = _entry(provider="anthropic", auth="LEXBENCH_TEST_CREDENTIAL", options={"retries": 1})
    assert AnthropicProvider(one, Path("unused"))._client().max_retries == 1


def test_l4_estimate_prices_every_permitted_attempt() -> None:
    paid = {"input_per_mtok": 3.0, "output_per_mtok": 15.0}
    reqs = [Request(f"c{i}", "system", "prompt " * 20, 64) for i in range(5)]
    once = make_provider(_entry(pricing=paid, options={"retries": 0}), Path("u")).estimate(reqs)
    assert once.attempts == 1
    for retries, options in (
        (1, {"retries": 1}),
        (2, {"retries": 2}),
        (3, {"retries": 3}),
        (3, {}),
    ):
        entry = _entry(pricing=paid, options=options)
        est = make_provider(entry, Path("u")).estimate(reqs)
        assert est.attempts == retries + 1
        assert (est.input_tokens, est.output_tokens) == (once.input_tokens, once.output_tokens)
        single = entry.pricing.usd(once.input_tokens, once.output_tokens, batch=False)
        assert est.usd == round(single * (retries + 1), 4)
    batch = _entry(pricing=paid, batch=True, options={"retries": 3})
    est = make_provider(batch, Path("u")).estimate(reqs)
    assert est.attempts == 1
    assert est.usd == round(batch.pricing.usd(once.input_tokens, once.output_tokens, True), 4)


def test_l4_estimate_without_the_attempt_count_is_refused_for_a_sync_entry(
    layout: Layout,
) -> None:
    _edit_registry(layout, {"mock-paid": {"batch": False}})
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-paid"], fetch_prices=False)
    est = read_json(layout.estimate)
    del est["entries"]["mock-paid"]["routing"]["attempts"]
    write_json(layout.estimate, est)
    with pytest.raises(runner.CapExceeded, match="attempts"):
        runner.run(layout, reg, "routing", "mock-paid", log=QUIET)


# L5: a synchronous run left 'running' by a dead process does not block for ever.


def _running_record(layout: Layout, reg: Any, family: str, model: str, **extra: Any) -> None:
    record = {
        "run_id": "run_fabricated",
        "family": family,
        "model": model,
        "provider": "mock",
        "provider_model": "mock-oracle-1",
        "request_count": 1,
        "estimated_usd": 0.0,
        "data_sha256": family_sha(layout, family),
        "config_sha256": reg.get(model).fingerprint(family),
        "submitted_at": utc_now(),
        "status": "running",
        "counts": {},
        "ended_at": None,
    }
    record.update(extra)
    write_json(layout.runs, {"schema_version": 1, "runs": [record]})


def _dead_pid() -> int:
    proc = subprocess.Popen([sys.executable, "-c", "pass"])
    proc.wait()
    return proc.pid


def test_l5_running_record_of_a_dead_process_is_failed_and_run_proceeds(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-sync"], fetch_prices=False)
    _running_record(layout, reg, "routing", "mock-sync", pid=_dead_pid(), heartbeat_at=utc_now())
    ids = runner.run(layout, reg, "routing", "mock-sync", log=QUIET)
    runs = read_json(layout.runs)["runs"]
    assert runs[0]["status"] == "failed" and "not running" in runs[0]["error"]
    assert runs[1]["run_id"] == ids[0] and runs[1]["status"] == "completed"
    assert read_jsonl(layout.graded_path("routing", "mock-sync"))


def test_l5_grade_fails_a_running_record_with_an_old_heartbeat(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    _running_record(
        layout, reg, "routing", "mock-sync", pid=os.getpid(), heartbeat_at="2026-01-01T00:00:00Z"
    )
    said: list[str] = []
    assert runner.grade(layout, reg, "routing", "mock-sync", log=said.append) is None
    run = read_json(layout.runs)["runs"][0]
    assert run["status"] == "failed" and "heartbeat" in run["error"]
    assert not any("in progress" in s for s in said)


def test_l5_live_running_record_blocks_a_second_run(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-sync"], fetch_prices=False)
    _running_record(layout, reg, "routing", "mock-sync", pid=os.getpid(), heartbeat_at=utc_now())
    with pytest.raises(runner.CapExceeded, match="running"):
        runner.run(layout, reg, "routing", "mock-sync", log=QUIET)
    assert len(read_json(layout.runs)["runs"]) == 1


def test_l5_run_records_pid_and_refreshes_the_heartbeat(
    layout: Layout, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-sync"], fetch_prices=False)
    ticks = iter(range(10**6))
    monkeypatch.setattr(runner, "HEARTBEAT_SECONDS", 0.02)
    monkeypatch.setattr(
        runner,
        "utc_now",
        lambda: (lambda n: f"2026-11-11T00:{n // 60 % 60:02d}:{n % 60:02d}Z")(next(ticks)),
    )
    seen: list[dict[str, Any]] = []
    real = MockProvider.run_sync

    def slow(self: MockProvider, requests: Any) -> Any:
        seen.append(dict(read_json(layout.runs)["runs"][-1]))
        time.sleep(0.3)
        seen.append(dict(read_json(layout.runs)["runs"][-1]))
        return real(self, requests)

    monkeypatch.setattr(MockProvider, "run_sync", slow)
    runner.run(layout, reg, "routing", "mock-sync", log=QUIET)
    assert seen[0]["pid"] == os.getpid()
    assert seen[0]["heartbeat_at"] and seen[1]["heartbeat_at"] != seen[0]["heartbeat_at"]


# L6: a pending record that has a batch id is polled; the refusal names a working recovery.


def test_l6_pending_record_with_batch_id_is_polled_and_does_not_block(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock"], fetch_prices=False)
    from lexbench.build import load_cases
    from lexbench.families import to_request

    requests = [to_request(c) for c in load_cases(layout, "routing")]
    batch_id = MockProvider(reg.get("mock"), layout.cache).submit_batch(requests)
    write_json(
        layout.batches,
        {
            "schema_version": 1,
            "batches": [
                {
                    "batch_id": batch_id,
                    "submission_id": "sub_routing_mock_1",
                    "family": "routing",
                    "model": "mock",
                    "provider": "mock",
                    "provider_model": "mock-oracle-1",
                    "request_count": len(requests),
                    "estimated_usd": 0.0,
                    "data_sha256": family_sha(layout, "routing"),
                    "config_sha256": reg.get("mock").fingerprint("routing"),
                    "chunk": "1/1",
                    "submitted_at": "2026-11-11T00:00:00Z",
                    "status": "pending",
                    "counts": {},
                    "ended_at": None,
                }
            ],
        },
    )
    said: list[str] = []
    assert runner.run(layout, reg, "routing", "mock", log=said.append) == [batch_id]
    assert "nothing to do" in said[-1]
    tally = runner.poll(layout, reg, log=QUIET)
    assert tally["ended"] == 1 and tally["pending"] == 0
    assert read_json(layout.batches)["batches"][0]["status"] == "ended"
    assert len(read_jsonl(layout.graded_path("routing", "mock"))) == len(requests)


def test_l6_refusal_describes_the_recovery_that_works(
    layout: Layout, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock"], fetch_prices=False)

    def crash(*_a: object, **_k: object) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(MockProvider, "submit_batch", crash)
    with pytest.raises(KeyboardInterrupt):
        runner.run(layout, reg, "routing", "mock", log=QUIET)
    with pytest.raises(runner.CapExceeded) as refused:
        runner.run(layout, reg, "routing", "mock", log=QUIET)
    message = str(refused.value)
    assert "batch_id" in message and "status" in message and "failed" in message
