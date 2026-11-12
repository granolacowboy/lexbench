"""Estimate arithmetic and the spend cap, enforced before each submission."""

from __future__ import annotations

import pytest

from lexbench.estimate import estimate
from lexbench.paths import Layout
from lexbench.providers import make_provider
from lexbench.providers.base import estimate_tokens
from lexbench.records import Request, read_json, write_json
from lexbench.registry import load_registry
from lexbench.runner import CapExceeded, check_cap, recorded_spend, run


def test_token_heuristic() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abc") == 1
    assert estimate_tokens("abcd") == 2


def test_pricing_arithmetic(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    entry = reg.get("mock-paid")
    # 1,000,000 input and 100,000 output tokens: (3 + 1.5) USD, halved by the batch discount.
    assert entry.pricing.usd(1_000_000, 100_000, batch=True) == pytest.approx(2.25)
    assert entry.pricing.usd(1_000_000, 100_000, batch=False) == pytest.approx(4.5)
    provider = make_provider(entry, layout.cache)
    req = Request("x", "s" * 30, "p" * 300, max_tokens=24)
    est = provider.estimate([req, req])
    assert est.input_tokens == 2 * (10 + 100 + 16)
    assert est.output_tokens == 48
    expected = (252 * 3.0 + 48 * 15.0) / 1e6 * 0.5
    assert est.usd == pytest.approx(round(expected, 4))


def test_check_cap_boundary() -> None:
    check_cap(59.0, 1.0, 60.0)
    with pytest.raises(CapExceeded):
        check_cap(59.0, 1.01, 60.0)


def test_free_entries_count_as_zero(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    out = estimate(layout, reg, ["mock"], fetch_prices=False)
    assert out["totals_usd"]["mock"] == 0.0
    assert out["within_cap"]


def test_run_refuses_over_cap_before_submitting(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-paid"], fetch_prices=False)
    est = read_json(layout.estimate)
    family_usd = est["entries"]["mock-paid"]["routing"]["usd"]
    assert family_usd > 0
    # Pre-record spend so that this submission would cross the cap.
    write_json(
        layout.runs,
        {
            "schema_version": 1,
            "runs": [
                {
                    "run_id": "earlier",
                    "family": "other",
                    "model": "x",
                    "request_count": 1,
                    "estimated_usd": reg.spend_cap_usd - family_usd / 2,
                    "data_sha256": "",
                    "submitted_at": "2026-01-01T00:00:00Z",
                    "status": "completed",
                }
            ],
        },
    )
    with pytest.raises(CapExceeded):
        run(layout, reg, "routing", "mock-paid", log=lambda _s: None)
    assert read_json(layout.batches) is None
    assert not (layout.cache / "mock").exists()


def test_run_refuses_stale_or_missing_estimate(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    with pytest.raises(CapExceeded, match="missing"):
        run(layout, reg, "routing", "mock-paid", log=lambda _s: None)
    estimate(layout, reg, ["mock-paid"], fetch_prices=False)
    est = read_json(layout.estimate)
    est["data"]["routing"] = "0" * 64
    write_json(layout.estimate, est)
    with pytest.raises(CapExceeded, match="stale"):
        run(layout, reg, "routing", "mock-paid", log=lambda _s: None)


def test_recorded_spend_sums_batches_and_runs(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-paid"], fetch_prices=False)
    run(layout, reg, "routing", "mock-paid", log=lambda _s: None)
    est = read_json(layout.estimate)["entries"]["mock-paid"]["routing"]["usd"]
    assert recorded_spend(layout) == pytest.approx(est, abs=1e-4)
