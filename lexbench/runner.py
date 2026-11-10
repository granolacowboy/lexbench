"""`lexbench run`, `poll` and `grade`, with the spend cap and idempotent state.

Every submission is recorded before its results are awaited: batches in state/batches.json
(batch id, family, model name, request count, estimated USD) and synchronous runs in
state/runs.json. The cap is enforced before each submission from results/estimate.json and
the recorded submissions, never after.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from graders import GRADERS
from lexbench.build import family_sha, load_cases
from lexbench.families import to_request
from lexbench.paths import Layout
from lexbench.providers import make_provider
from lexbench.records import (
    Response,
    chunked,
    read_json,
    read_jsonl,
    utc_now,
    write_json,
    write_jsonl,
)
from lexbench.registry import Registry

Log = Callable[[str], None]
SKIP_STATUSES = {"failed"}


class CapExceeded(RuntimeError):
    pass


def _load(layout: Layout, kind: str) -> dict[str, Any]:
    path = layout.batches if kind == "batches" else layout.runs
    state: dict[str, Any] = read_json(path, default=None) or {"schema_version": 1, kind: []}
    return state


def _save(layout: Layout, kind: str, state: dict[str, Any]) -> None:
    write_json(layout.batches if kind == "batches" else layout.runs, state)


def recorded_spend(layout: Layout) -> float:
    total = sum(float(b["estimated_usd"]) for b in _load(layout, "batches")["batches"])
    total += sum(float(r["estimated_usd"]) for r in _load(layout, "runs")["runs"])
    return round(total, 4)


def _estimate_for(layout: Layout, family: str, model: str) -> dict[str, Any]:
    est = read_json(layout.estimate, default=None)
    if not est:
        raise CapExceeded("refused: results/estimate.json is missing; run `lexbench estimate`")
    if est.get("data", {}).get(family) != family_sha(layout, family):
        raise CapExceeded(f"refused: the estimate for {family} is stale; run `lexbench estimate`")
    try:
        entry: dict[str, Any] = est["entries"][model][family]
    except KeyError as exc:
        raise CapExceeded(f"refused: no estimate for {family} on {model}") from exc
    return entry


def check_cap(spent: float, new_usd: float, cap: float) -> None:
    if spent + new_usd > cap + 1e-9:
        raise CapExceeded(
            f"refused: recorded {spent:.2f} USD plus this submission {new_usd:.2f} USD "
            f"exceeds the cap of {cap:.2f} USD"
        )


def _records_for(
    layout: Layout, registry: Registry, family: str, model: str
) -> list[dict[str, Any]]:
    """Submissions for this family and entry made with the current data and settings."""
    sha = family_sha(layout, family)
    config = registry.get(model).fingerprint()

    def current(r: dict[str, Any]) -> bool:
        return (
            r["family"] == family
            and r["model"] == model
            and r["data_sha256"] == sha
            and r.get("config_sha256") == config
        )

    out = [
        dict(b, kind="batch", sid=b["batch_id"])
        for b in _load(layout, "batches")["batches"]
        if current(b)
    ]
    out += [
        dict(r, kind="run", sid=r["run_id"]) for r in _load(layout, "runs")["runs"] if current(r)
    ]
    return sorted(out, key=lambda r: str(r["submitted_at"]))


def run(layout: Layout, registry: Registry, family: str, model: str, log: Log = print) -> list[str]:
    entry = registry.get(model)
    existing = [
        r for r in _records_for(layout, registry, family, model) if r["status"] not in SKIP_STATUSES
    ]
    if any(r["kind"] == "batch" or r["status"] == "completed" for r in existing):
        known = [str(r["sid"]) for r in existing]
        log(f"{family} on {model}: already submitted ({', '.join(known)}); nothing to do")
        return known
    cases = load_cases(layout, family)
    requests = [to_request(c) for c in cases]
    est = _estimate_for(layout, family, model)
    per_request = (float(est["usd"]) / len(requests)) if requests and est["paid"] else 0.0
    provider = make_provider(entry, layout.cache)
    sha = family_sha(layout, family)
    ids: list[str] = []
    if entry.batch:
        chunks = list(chunked(requests, registry.max_requests_per_batch))
        for i, chunk in enumerate(chunks, start=1):
            usd = round(per_request * len(chunk), 4)
            check_cap(recorded_spend(layout), usd, registry.spend_cap_usd)
            batch_id = provider.submit_batch(chunk)
            state = _load(layout, "batches")
            state["batches"].append(
                {
                    "batch_id": batch_id,
                    "family": family,
                    "model": model,
                    "provider": entry.provider,
                    "provider_model": entry.model,
                    "request_count": len(chunk),
                    "estimated_usd": usd,
                    "data_sha256": sha,
                    "config_sha256": entry.fingerprint(),
                    "chunk": f"{i}/{len(chunks)}",
                    "submitted_at": utc_now(),
                    "status": "in_progress",
                    "counts": {},
                    "ended_at": None,
                }
            )
            _save(layout, "batches", state)
            ids.append(batch_id)
            log(
                f"{family} on {model}: submitted batch {batch_id} ({len(chunk)} requests, "
                f"estimated {usd:.2f} USD)"
            )
        return ids
    usd = round(per_request * len(requests), 4)
    check_cap(recorded_spend(layout), usd, registry.spend_cap_usd)
    run_id = f"run_{family}_{model}_{utc_now().replace(':', '').replace('-', '')}"
    state = _load(layout, "runs")
    record = {
        "run_id": run_id,
        "family": family,
        "model": model,
        "provider": entry.provider,
        "provider_model": entry.model,
        "request_count": len(requests),
        "estimated_usd": usd,
        "data_sha256": sha,
        "config_sha256": entry.fingerprint(),
        "submitted_at": utc_now(),
        "status": "running",
        "counts": {},
        "ended_at": None,
    }
    state["runs"].append(record)
    _save(layout, "runs", state)
    log(
        f"{family} on {model}: synchronous run {run_id} ({len(requests)} requests, "
        f"concurrency {entry.concurrency}, estimated {usd:.2f} USD)"
    )
    responses = provider.run_sync(requests)
    write_jsonl(layout.raw_path(family, model, run_id), [r.to_json() for r in responses])
    state = _load(layout, "runs")
    for r in state["runs"]:
        if r["run_id"] == run_id:
            r["status"] = "completed"
            r["ended_at"] = utc_now()
            r["counts"] = {
                "succeeded": sum(1 for x in responses if x.error is None),
                "errored": sum(1 for x in responses if x.error is not None),
            }
    _save(layout, "runs", state)
    grade(layout, registry, family, model, log)
    return [run_id]


def poll(
    layout: Layout, registry: Registry, log: Log = print, do_grade: bool = True
) -> dict[str, int]:
    state = _load(layout, "batches")
    tally = {"in_progress": 0, "ended": 0}
    ended_now: set[tuple[str, str]] = set()
    for b in state["batches"]:
        if b["status"] != "in_progress":
            if b["status"] == "ended":
                tally["ended"] += 1
            continue
        provider = make_provider(registry.get(b["model"]), layout.cache)
        try:
            status = provider.poll_batch(b["batch_id"])
            responses = provider.fetch_batch(b["batch_id"]) if status.status == "ended" else []
        except Exception as exc:  # one unreachable batch must not stop the others
            log(
                f"{b['batch_id']} ({b['family']} on {b['model']}): poll failed, "
                f"{type(exc).__name__}; retried at the next poll"
            )
            tally["in_progress"] += 1
            continue
        b["counts"] = status.counts
        b["polled_at"] = utc_now()
        if status.status == "ended":
            write_jsonl(
                layout.raw_path(b["family"], b["model"], b["batch_id"]),
                [r.to_json() for r in responses],
            )
            b["status"] = "ended"
            b["ended_at"] = utc_now()
            ended_now.add((b["family"], b["model"]))
            tally["ended"] += 1
        else:
            tally["in_progress"] += 1
        log(f"{b['batch_id']} ({b['family']} on {b['model']}): {b['status']} {b['counts']}")
        _save(layout, "batches", state)
    _save(layout, "batches", state)
    if do_grade:
        for family, model in sorted(ended_now):
            grade(layout, registry, family, model, log)
    return tally


def grade(
    layout: Layout, registry: Registry, family: str, model: str, log: Log = print
) -> dict[str, Any] | None:
    records = _records_for(layout, registry, family, model)
    live = [r for r in records if r["status"] not in SKIP_STATUSES]
    if not live:
        log(f"{family} on {model}: no submissions to grade")
        return None
    if any(r["status"] not in {"ended", "completed"} for r in live):
        log(f"{family} on {model}: submissions still in progress; not graded")
        return None
    responses: dict[str, Response] = {}
    for r in live:
        path = layout.raw_path(family, model, r["sid"])
        if path.is_file():
            for row in read_jsonl(path):
                responses[row["custom_id"]] = Response.from_json(row)
    grader = GRADERS[family]
    out = []
    correct = 0
    for case in load_cases(layout, family):
        resp = responses.get(case["id"])
        if resp is None:
            verdict_ok, reason, text = False, "no response recorded", None
        elif resp.error:
            verdict_ok, reason, text = False, f"provider error: {resp.error}", None
        else:
            v = grader(case["expected"], resp.text)
            verdict_ok, reason, text = v.correct, v.reason, resp.text
        correct += int(verdict_ok)
        out.append(
            {
                "id": case["id"],
                "group": case["group"],
                "expected": case["expected"],
                "response": text,
                "correct": verdict_ok,
                "reason": reason,
                "input_tokens": resp.input_tokens if resp else 0,
                "output_tokens": resp.output_tokens if resp else 0,
            }
        )
    write_jsonl(layout.graded_path(family, model), out)
    summary = {
        "family": family,
        "model": model,
        "n": len(out),
        "correct": correct,
        "accuracy": round(correct / len(out), 4) if out else 0.0,
    }
    log(f"graded {family} on {model}: {correct}/{len(out)} correct")
    return summary
