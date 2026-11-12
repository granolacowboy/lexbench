"""The lexbench command line: models, build, estimate, run, poll, grade, report."""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from collections.abc import Sequence

from lexbench import build as build_mod
from lexbench import estimate as estimate_mod
from lexbench import report as report_mod
from lexbench import runner
from lexbench.paths import FAMILIES, Layout, default_root
from lexbench.providers import PROVIDERS, ProviderError, make_provider
from lexbench.registry import Registry, RegistryError, load_registry


def _registry(layout: Layout) -> Registry:
    return load_registry(layout.models_yaml, set(PROVIDERS))


def cmd_models(layout: Layout, args: argparse.Namespace) -> int:
    reg = _registry(layout)
    print(
        f"registry valid: {len(reg.entries)} entries, cap {reg.spend_cap_usd:.2f} USD, "
        f"at most {reg.max_requests_per_batch} requests per batch"
    )
    failures = 0
    listings: dict[tuple[str, str | None, str | None], list[str] | str] = {}
    for e in reg.entries.values():
        status = "not verified (offline)"
        if not args.offline:
            key = (e.provider, e.endpoint, e.auth)
            if key not in listings:
                try:
                    listings[key] = make_provider(e, layout.cache).list_models()
                except (ProviderError, OSError, RuntimeError) as exc:
                    listings[key] = f"unreachable: {str(exc)[:80]}"
                except Exception as exc:  # provider SDK and HTTP errors vary by adapter
                    listings[key] = f"unreachable: {type(exc).__name__}"
            found = listings[key]
            if isinstance(found, str):
                status = found
                if e.provider == "anthropic":
                    failures += 1
            elif e.model in found:
                status = "verified"
            else:
                status = "NOT FOUND in provider list"
                failures += 1
        price = f"{e.pricing.input_per_mtok:g}/{e.pricing.output_per_mtok:g} USD per MTok" + (
            f", batch discount {e.pricing.batch_discount:g}" if e.pricing.batch_discount else ""
        )
        print(
            f"  {e.name}: provider {e.provider}, model {e.model}, batch {str(e.batch).lower()}, "
            f"{price}: {status}"
        )
    return 1 if failures else 0


def cmd_build(layout: Layout, args: argparse.Namespace) -> int:
    families = args.family or list(FAMILIES)
    manifest = build_mod.build(layout, families, args.sample, refresh=args.refresh)
    for f in families:
        entry = manifest["families"][f]
        print(
            f"built {f}: {entry['count']} cases in {len(entry['files'])} files, "
            f"sha256 {entry['sha256'][:16]}"
        )
    return 0


def cmd_estimate(layout: Layout, args: argparse.Namespace) -> int:
    reg = _registry(layout)
    out = estimate_mod.estimate(layout, reg, args.model, fetch_prices=not args.no_fetch)
    pc = out["pricing_check"]
    print(f"pricing check: {pc['status']} ({pc['url']}, fetched {pc['fetched_at']})")
    for name, per in out["entries"].items():
        parts = ", ".join(f"{f} {v['requests']} req {v['usd']:.2f} USD" for f, v in per.items())
        print(f"  {name}: {parts}; total {out['totals_usd'][name]:.2f} USD")
    print(
        f"total {out['total_usd']:.2f} USD against cap {out['spend_cap_usd']:.2f} USD: "
        + ("within cap" if out["within_cap"] else "EXCEEDS CAP")
    )
    return 0 if out["within_cap"] else 2


def cmd_run(layout: Layout, args: argparse.Namespace) -> int:
    reg = _registry(layout)
    families = list(FAMILIES) if args.family == "all" else [args.family]
    for f in families:
        runner.run(layout, reg, f, args.model)
    return 0


def cmd_poll(layout: Layout, args: argparse.Namespace) -> int:
    tally = runner.poll(layout, _registry(layout), do_grade=not args.no_grade)
    pending = f", pending {tally['pending']}" if tally.get("pending") else ""
    error = f", error {tally['error']}" if tally.get("error") else ""
    print(f"batches ended {tally['ended']}, in progress {tally['in_progress']}{pending}{error}")
    return 0


def cmd_grade(layout: Layout, args: argparse.Namespace) -> int:
    reg = _registry(layout)
    families = args.family or list(FAMILIES)
    models = args.model or list(reg.entries)
    refused = 0
    for f in families:
        for m in models:
            said: list[str] = []
            result = runner.grade(layout, reg, f, m, log=said.append)
            if result is None:
                # Nothing was graded; an existing results file is not current and is not
                # reported as graded (`lexbench report` excludes it).
                refused += 1
                reason = said[-1] if said else f"{f} on {m}: not graded"
                print(f"not graded: {reason}", file=sys.stderr)
                continue
            path = layout.graded_path(f, m)
            print(
                f"graded {f} on {m}: {path.relative_to(layout.root)} "
                f"({result['correct']}/{result['n']} correct)"
            )
    return 1 if refused else 0


def cmd_report(layout: Layout, args: argparse.Namespace) -> int:
    summary = report_mod.report(layout, _registry(layout))
    for x in summary.get("excluded", []):
        print(f"excluded {x['family']} on {x['model']}: {x['reason']}", file=sys.stderr)
    print(report_mod.table(summary), end="")
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lexbench", description=__doc__)
    p.add_argument("--root", help="repository root (default: nearest parent with models.yaml)")
    sub = p.add_subparsers(dest="command", required=True)
    s = sub.add_parser("models", help="list and validate the model registry")
    s.add_argument("--offline", action="store_true", help="validate without provider listings")
    s = sub.add_parser("build", help="materialise the task families into data/")
    s.add_argument("--family", action="append", choices=FAMILIES)
    s.add_argument("--sample", type=int, help="LegalBench examples per task (default 100)")
    s.add_argument(
        "--refresh",
        action="store_true",
        help="renew the manifest built_at and the license fetch times even when unchanged",
    )
    s = sub.add_parser("estimate", help="token and USD estimate; submits nothing")
    s.add_argument("--model", action="append")
    s.add_argument("--no-fetch", action="store_true", help="skip the pricing page check")
    s = sub.add_parser("run", help="run one family on one model entry")
    s.add_argument("--family", required=True, choices=[*FAMILIES, "all"])
    s.add_argument("--model", required=True)
    s = sub.add_parser("poll", help="record batch status; download and grade ended batches")
    s.add_argument("--no-grade", action="store_true")
    s = sub.add_parser("grade", help="grade recorded responses")
    s.add_argument("--family", action="append", choices=FAMILIES)
    s.add_argument("--model", action="append")
    sub.add_parser("report", help="write results/summary.json and the README table")
    return p


COMMANDS = {
    "models": cmd_models,
    "build": cmd_build,
    "estimate": cmd_estimate,
    "run": cmd_run,
    "poll": cmd_poll,
    "grade": cmd_grade,
    "report": cmd_report,
}


def workspace_env(layout: Layout) -> None:
    """Keep caches and temporary files inside the workspace.

    HF_HOME (the datasets cache of `lexbench build`) and TMPDIR default to directories under
    .lexbench-cache in the repository root; a value already set in the environment is kept.
    """
    defaults = {"HF_HOME": layout.cache / "hf", "TMPDIR": layout.cache / "tmp"}
    for var, path in defaults.items():
        if not os.environ.get(var):
            path.mkdir(parents=True, exist_ok=True)
            os.environ[var] = str(path)
    tempfile.tempdir = None  # re-read TMPDIR on the next call


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    from pathlib import Path

    layout = Layout(Path(args.root).resolve() if args.root else default_root())
    workspace_env(layout)
    try:
        return COMMANDS[args.command](layout, args)
    except runner.CapExceeded as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (RegistryError, ProviderError, RuntimeError, ValueError) as exc:
        print(f"error: {str(exc)[:300]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
