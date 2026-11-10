"""Regression tests for the findings of review XREVIEW-LEXBENCH-1, one or more per finding.

Each test was written before its fix and failed against head 224b4da.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest
import yaml

from graders import grade_legalbench
from lexbench import build as build_mod
from lexbench import cli, runner
from lexbench.estimate import estimate
from lexbench.families import fragments, legalbench
from lexbench.paths import Layout
from lexbench.providers import ProviderError, make_provider
from lexbench.providers.mock import MockProvider
from lexbench.records import Request, read_json, read_jsonl
from lexbench.registry import load_registry, parse_registry
from tests.conftest import REGISTRY, REPO


def QUIET(_s: str) -> None:
    return None


def _patch_entry(layout: Layout, name: str, extra: dict[str, Any]) -> None:
    raw = yaml.safe_load(layout.models_yaml.read_text(encoding="utf-8"))
    raw["models"][name].update(extra)
    layout.models_yaml.write_text(yaml.safe_dump(raw), encoding="utf-8")


# F1: the cap must not accept an estimate made under other entry settings or prices.


def test_f1_estimate_records_fingerprint_and_pricing(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-paid"], fetch_prices=False)
    per = read_json(layout.estimate)["entries"]["mock-paid"]["routing"]
    entry = reg.get("mock-paid")
    assert per["config_sha256"] == entry.fingerprint("routing")
    assert per["pricing"] == {"input_per_mtok": 3.0, "output_per_mtok": 15.0, "batch_discount": 0.5}


def test_f1_run_refuses_estimate_made_under_other_settings(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-paid"], fetch_prices=False)
    _patch_entry(layout, "mock-paid", {"reasoning_tokens": 4096})
    reg = load_registry(layout.models_yaml)
    with pytest.raises(runner.CapExceeded, match="settings"):
        runner.run(layout, reg, "routing", "mock-paid", log=QUIET)
    assert read_json(layout.batches) is None


def test_f1_run_refuses_estimate_made_under_other_prices(layout: Layout) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-paid"], fetch_prices=False)
    _patch_entry(
        layout, "mock-paid", {"pricing": {"input_per_mtok": 30.0, "output_per_mtok": 150.0}}
    )
    reg = load_registry(layout.models_yaml)
    with pytest.raises(runner.CapExceeded, match="pricing"):
        runner.run(layout, reg, "routing", "mock-paid", log=QUIET)
    assert read_json(layout.batches) is None


# F5: a failed synchronous run is recorded as failed, and grading proceeds afterwards.


def test_f5_failed_sync_run_is_recorded_failed_and_does_not_block(
    layout: Layout, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-sync"], fetch_prices=False)

    def broken(*_a: object, **_k: object) -> list[object]:
        raise ProviderError("environment variable X is EMPTY")

    with monkeypatch.context() as m:
        m.setattr(MockProvider, "run_sync", broken)
        with pytest.raises(ProviderError):
            runner.run(layout, reg, "routing", "mock-sync", log=QUIET)
    runs = read_json(layout.runs)["runs"]
    assert [r["status"] for r in runs] == ["failed"]
    assert runs[0]["ended_at"] and "ProviderError" in runs[0]["error"]
    runner.run(layout, reg, "routing", "mock-sync", log=QUIET)
    assert runner.grade(layout, reg, "routing", "mock-sync", log=QUIET) is not None
    rows = read_jsonl(layout.graded_path("routing", "mock-sync"))
    assert rows and all(r["correct"] for r in rows)


# F6: the prefix rule never reads a wrong answer as right.

INSURANCE = {"label": "A", "labels": ["A", "B", "C"]}
YES = {"label": "Yes", "labels": ["No", "Yes"]}


@pytest.mark.parametrize(
    "expected, response",
    [
        (INSURANCE, "A reasonable reader would find the claim is not covered, so B."),
        (YES, "Yes or no: the answer is no."),
        (YES, "Yes and no are both possible here; No."),
    ],
)
def test_f6_prefix_rule_rejects_wrong_to_right(expected: dict[str, Any], response: str) -> None:
    assert not grade_legalbench(expected, response).correct


def test_f6_prefix_rule_still_reads_a_label_with_a_reason() -> None:
    assert grade_legalbench(YES, "Yes, because the statement is offered for its truth.").correct
    assert grade_legalbench({"label": "B", "labels": ["A", "B", "C"]}, "B").correct
    assert grade_legalbench({"label": "B", "labels": ["A", "B", "C"]}, "B.").correct


# F13: the LegalBench grader reads the whole response; the last label line is the answer.


@pytest.mark.parametrize(
    "label, response",
    [
        ("No", "Both parties are from North Carolina, so there is no complete diversity.\n\nA: No"),
        ("No", "The total cost was truthfully presented and there is no violation.\n\nNo"),
        ("UCC", "Buying a sandwich is a sale of goods.\n\nGoverned by: UCC"),
    ],
)
def test_f13_answer_after_reasoning_is_read(label: str, response: str) -> None:
    labels = ["Common Law", "UCC"] if label == "UCC" else ["No", "Yes"]
    assert grade_legalbench({"label": label, "labels": labels}, response).correct


def test_f13_last_label_line_wins() -> None:
    gold_no = {"label": "No", "labels": ["No", "Yes"]}
    assert grade_legalbench(gold_no, "Yes\n\nOn reflection the rule is not met.\n\nNo").correct
    assert not grade_legalbench(gold_no, "No\n\nOn reflection the rule is met.\n\nYes").correct


# F15: a rebuild leaves tracked provenance unchanged unless --refresh is given.


def test_f15_rebuild_keeps_built_at_unless_refresh(
    layout: Layout, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = read_json(layout.manifest)["families"]["routing"]["built_at"]
    monkeypatch.setattr(build_mod, "utc_now", lambda: "2099-01-01T00:00:00Z")
    build_mod.build(layout, ["routing"])
    assert read_json(layout.manifest)["families"]["routing"]["built_at"] == before
    build_mod.build(layout, ["routing"], refresh=True)
    assert read_json(layout.manifest)["families"]["routing"]["built_at"] == "2099-01-01T00:00:00Z"


def test_f15_license_fetch_times_are_kept_unless_refresh() -> None:
    prov = {
        "upstream": "u/r",
        "upstream_commit": "c",
        "dataset": "d/s",
        "dataset_revision": "r",
        "excluded": [],
    }
    url = "https://example.org/README.md"
    old = [legalbench.LicenseEvidence("t", "CC BY 4.0", True, url, "2026-01-01T00:00:00Z", "l")]
    previous = legalbench.licenses_markdown(old, prov, {"t": "x"})
    new = [legalbench.LicenseEvidence("t", "CC BY 4.0", True, url, "2026-12-31T00:00:00Z", "l")]
    kept = legalbench.keep_fetch_times(new, previous)
    assert kept[0].fetched_at == "2026-01-01T00:00:00Z"
    changed = [legalbench.LicenseEvidence("t", "MIT", True, url, "2026-12-31T00:00:00Z", "l")]
    assert legalbench.keep_fetch_times(changed, previous)[0].fetched_at == "2026-12-31T00:00:00Z"


# F16: a batch is recorded as pending before the provider is called, then updated.


def test_f16_batch_recorded_pending_before_provider_call(
    layout: Layout, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-paid"], fetch_prices=False)
    seen: list[list[dict[str, Any]]] = []
    original = MockProvider.submit_batch

    def spy(self: MockProvider, requests: Any) -> str:
        seen.append(read_json(layout.batches)["batches"])
        return original(self, requests)

    monkeypatch.setattr(MockProvider, "submit_batch", spy)
    ids = runner.run(layout, reg, "routing", "mock-paid", log=QUIET)
    assert len(seen) == 1 and len(seen[0]) == 1
    assert seen[0][0]["status"] == "pending" and seen[0][0]["batch_id"] is None
    assert seen[0][0]["estimated_usd"] > 0
    final = read_json(layout.batches)["batches"]
    assert [b["batch_id"] for b in final] == ids
    assert final[0]["status"] == "in_progress"


def test_f16_crash_after_submit_is_counted_and_blocks_a_resubmission(
    layout: Layout, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-paid"], fetch_prices=False)

    def crash(*_a: object, **_k: object) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(MockProvider, "submit_batch", crash)
    with pytest.raises(KeyboardInterrupt):
        runner.run(layout, reg, "routing", "mock-paid", log=QUIET)
    batches = read_json(layout.batches)["batches"]
    assert batches[0]["status"] == "pending"
    assert runner.recorded_spend(layout) == pytest.approx(batches[0]["estimated_usd"])
    monkeypatch.undo()
    with pytest.raises(runner.CapExceeded, match="pending"):
        runner.run(layout, reg, "routing", "mock-paid", log=QUIET)


def test_f16_provider_refusal_is_recorded_failed(
    layout: Layout, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg = load_registry(layout.models_yaml)
    estimate(layout, reg, ["mock-paid"], fetch_prices=False)

    def refuse(*_a: object, **_k: object) -> str:
        raise ProviderError("refused")

    monkeypatch.setattr(MockProvider, "submit_batch", refuse)
    with pytest.raises(ProviderError):
        runner.run(layout, reg, "routing", "mock-paid", log=QUIET)
    assert read_json(layout.batches)["batches"][0]["status"] == "failed"


# F17: the CLI keeps the datasets cache and temporary files inside the workspace.


def test_f17_cli_defaults_hf_home_and_tmpdir_inside_the_workspace(
    layout: Layout, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HF_HOME", raising=False)
    monkeypatch.delenv("TMPDIR", raising=False)
    monkeypatch.setattr(tempfile, "tempdir", None)
    assert cli.main(["--root", str(layout.root), "models", "--offline"]) == 0
    assert os.environ["HF_HOME"] == str(layout.cache / "hf")
    assert os.environ["TMPDIR"] == str(layout.cache / "tmp")
    assert Path(tempfile.gettempdir()) == layout.cache / "tmp"


def test_f17_cli_respects_variables_already_set(
    layout: Layout, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HF_HOME", str(tmp_path / "hf"))
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    assert cli.main(["--root", str(layout.root), "models", "--offline"]) == 0
    assert os.environ["HF_HOME"] == str(tmp_path / "hf")
    assert os.environ["TMPDIR"] == str(tmp_path)


# F18: the mock hash mode chooses among several fragment answers, not only the reference.


def test_f18_fragment_choices_are_not_an_oracle() -> None:
    rows = [r for pack in fragments.build(REPO / "sources").values() for r in pack]
    for r in rows:
        assert r["meta"]["reference"] in r["meta"]["choices"]
        assert len(r["meta"]["choices"]) >= 3, r["id"]


def test_f18_hash_mode_is_not_perfect_on_fragments(layout: Layout) -> None:
    text = layout.models_yaml.read_text(encoding="utf-8").replace("mode: oracle", "mode: hash", 1)
    layout.models_yaml.write_text(text, encoding="utf-8")
    root = ["--root", str(layout.root)]
    assert cli.main([*root, "estimate", "--no-fetch", "--model", "mock"]) == 0
    assert cli.main([*root, "run", "--family", "fragments", "--model", "mock"]) == 0
    assert cli.main([*root, "poll"]) == 0
    rows = read_jsonl(layout.graded_path("fragments", "mock"))
    share = sum(r["correct"] for r in rows) / len(rows)
    assert 0.0 < share < 0.6


# F10: the sampling temperature each adapter sends.


def test_f10_temperature_per_adapter(tmp_path: Path) -> None:
    raw = json.loads(json.dumps(REGISTRY))
    raw["models"]["claude"] = {
        "provider": "anthropic",
        "model": "claude-x",
        "pricing": {"input_per_mtok": 1, "output_per_mtok": 1},
        "max_tokens": 64,
        "concurrency": 1,
        "batch": True,
    }
    raw["models"]["local"] = {
        "provider": "openai_compatible",
        "model": "m",
        "endpoint": "http://localhost:1/v1",
        "pricing": {"input_per_mtok": 0, "output_per_mtok": 0},
        "max_tokens": 64,
        "concurrency": 1,
        "batch": False,
    }
    reg = parse_registry(raw)
    req = Request("x", "s", "p", 24)
    claude: Any = make_provider(reg.get("claude"), tmp_path)
    local: Any = make_provider(reg.get("local"), tmp_path)
    # The Claude 5.5 models reject any temperature from API version 2026-10-21, so the
    # Anthropic adapter sends none; the OpenAI-compatible adapter sends 0.
    assert not {"temperature", "top_p", "top_k"} & set(claude._params(req))
    assert local._body(req)["temperature"] == 0
    assert "temperature" in (REPO / "README.md").read_text(encoding="utf-8")
    assert "temperature" in (REPO / "docs" / "post-draft.md").read_text(encoding="utf-8")


# F12: the test case that repeats an upstream demonstration is excluded and recorded.


def test_f12_duplicated_demonstration_is_excluded() -> None:
    cfg = yaml.safe_load((REPO / "sources" / "legalbench" / "tasks.yaml").read_text())
    excluded = {e["id"]: e for e in cfg["exclude"]}
    assert "lb-decisionfn-0366" in excluded and excluded["lb-decisionfn-0366"]["reason"]
    rows = [{"id": "lb-decisionfn-0366"}, {"id": "lb-decisionfn-0001"}]
    kept, dropped = legalbench.apply_exclusions(rows, set(excluded))
    assert [r["id"] for r in kept] == ["lb-decisionfn-0001"]
    assert dropped == ["lb-decisionfn-0366"]
    manifest = read_json(REPO / "data" / "MANIFEST.json")["families"]["legalbench"]
    assert manifest["provenance"]["excluded"] == ["lb-decisionfn-0366"]
    licenses = (REPO / "data" / "legalbench" / "LICENSES.md").read_text(encoding="utf-8")
    assert "lb-decisionfn-0366" in licenses


# F14: the deadline prompt does not print each category's kind.


def test_f14_deadline_prompt_does_not_state_the_kind() -> None:
    rows = [r for pack in fragments.build(REPO / "sources").values() for r in pack]
    deadline = [r for r in rows if r["expected"]["case_kind"] == "deadline"]
    assert deadline
    for r in deadline:
        assert "(statutory)" not in r["prompt"] and "(firm_set)" not in r["prompt"], r["id"]
        assert "id, kind, name" not in r["prompt"]


# F2 and F11: the licence carve-out and the CC BY attribution.


def test_f2_notice_and_license_carve_out() -> None:
    notice = (REPO / "NOTICE.md").read_text(encoding="utf-8")
    license_text = (REPO / "LICENSE").read_text(encoding="utf-8")
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for text in (notice, license_text):
        for path in ("sources/mhsb/", "data/fragments/", "data/routing/"):
            assert path in text
        assert "LICENSE-SOURCE-AVAILABLE.md" in text
        assert "not licensed under" in text
    assert "[counsel review]" in readme


def test_f11_notice_carries_licence_uri_and_task_citations() -> None:
    notice = (REPO / "NOTICE.md").read_text(encoding="utf-8")
    assert "https://creativecommons.org/licenses/by/4.0/" in notice
    assert "arXiv:2103.06268" in notice  # cuad_audit_rights: Hendrycks et al. 2021
    assert "Zheng" in notice and "CaseHOLD" in notice  # overruling: Zheng et al. 2021
