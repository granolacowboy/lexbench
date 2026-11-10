"""`lexbench report`: results/summary.json and the README results table."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from lexbench.paths import FAMILIES, Layout
from lexbench.records import read_json, read_jsonl, utc_now, write_json
from lexbench.registry import Registry

START = "<!-- results:start -->"
END = "<!-- results:end -->"
PASS_BAR = Path(__file__).resolve().parents[1] / "graders" / "pass_bar.yaml"


FORMAT_FAILURES = (
    "empty response",
    "no label",
    "malformed",
    "no command",
    "provider error",
    "no response",
)


def _acc(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Accuracy, with the number of responses that could not be read as an answer."""
    n = len(rows)
    c = sum(1 for r in rows if r["correct"])
    unread = sum(1 for r in rows if str(r["reason"]).startswith(FORMAT_FAILURES))
    return {
        "n": n,
        "correct": c,
        "accuracy": round(c / n, 4) if n else 0.0,
        "format_failures": unread,
    }


def _balanced(rows: list[dict[str, Any]]) -> float:
    by_label: dict[str, list[bool]] = defaultdict(list)
    for r in rows:
        by_label[str(r["expected"].get("label"))].append(bool(r["correct"]))
    recalls = [sum(v) / len(v) for v in by_label.values() if v]
    return round(sum(recalls) / len(recalls), 4) if recalls else 0.0


def summarise(layout: Layout, registry: Registry, pass_bar_path: Path = PASS_BAR) -> dict[str, Any]:
    bars = yaml.safe_load(pass_bar_path.read_text(encoding="utf-8"))["families"]
    manifest = read_json(layout.manifest, default=None) or {"families": {}}
    reasoning = manifest["families"].get("legalbench", {}).get("tasks", {})
    models = [
        m for m in registry.entries if any(layout.graded_path(f, m).is_file() for f in FAMILIES)
    ]
    summary: dict[str, Any] = {"generated_at": utc_now(), "models": models, "families": {}}
    for family in FAMILIES:
        bar = bars.get(family, {}).get("pass_at_or_above")
        fam: dict[str, Any] = {"pass_bar": bar, "groups": {}, "overall": {}}
        for m in models:
            path = layout.graded_path(family, m)
            if not path.is_file():
                continue
            rows = read_jsonl(path)
            groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for r in rows:
                groups[r["group"]].append(r)
            for g, grows in sorted(groups.items()):
                stats = _acc(grows)
                if family == "legalbench":
                    stats["balanced_accuracy"] = _balanced(grows)
                    fam["groups"].setdefault(g, {"reasoning_type": reasoning.get(g, "")})
                fam["groups"].setdefault(g, {})[m] = stats
            overall = _acc(rows)
            if family == "legalbench":
                accs = [_acc(g)["accuracy"] for g in groups.values()]
                overall["mean_task_accuracy"] = round(sum(accs) / len(accs), 4) if accs else 0.0
            if family == "fragments":
                kinds: dict[str, list[dict[str, Any]]] = defaultdict(list)
                for r in rows:
                    kinds[r["expected"]["case_kind"]].append(r)
                overall["by_case_kind"] = {k: _acc(v) for k, v in sorted(kinds.items())}
            if bar is not None:
                overall["passes"] = overall["accuracy"] >= bar
            fam["overall"][m] = overall
        summary["families"][family] = fam
    write_json(layout.summary, summary)
    return summary


def _cell(stats: dict[str, Any] | None, key: str = "accuracy") -> str:
    return f"{stats[key]:.3f}" if stats else "n/a"


def table(summary: dict[str, Any]) -> str:
    models: list[str] = summary["models"]
    head = "| Family | Task or group | n | " + " | ".join(models) + " |"
    sep = "|---|---|---:|" + "---:|" * len(models)
    lines = [head, sep]
    fams = summary["families"]
    lb = fams.get("legalbench", {})
    for task, stats in lb.get("groups", {}).items():
        n = next((stats[m]["n"] for m in models if m in stats), 0)
        cells = " | ".join(_cell(stats.get(m)) for m in models)
        lines.append(f"| LegalBench | {task} ({stats.get('reasoning_type', '')}) | {n} | {cells} |")
    if lb.get("overall"):
        n = next((lb["overall"][m]["n"] for m in models if m in lb["overall"]), 0)
        cells = " | ".join(_cell(lb["overall"].get(m), "mean_task_accuracy") for m in models)
        lines.append(f"| LegalBench | mean of task accuracies | {n} | {cells} |")
    for family, label in (("fragments", "Fragment cases"), ("routing", "Routing")):
        fam = fams.get(family, {})
        if not fam.get("overall"):
            continue
        bar = fam.get("pass_bar")
        if family == "routing":
            for group, stats in fam.get("groups", {}).items():
                n = next((stats[m]["n"] for m in models if m in stats), 0)
                cells = " | ".join(_cell(stats.get(m)) for m in models)
                lines.append(f"| {label} | {group.replace('_', ' ')} | {n} | {cells} |")
        if family == "fragments":
            for kind in ("deadline", "flags"):
                per = {
                    m: fam["overall"][m]["by_case_kind"].get(kind)
                    for m in models
                    if m in fam["overall"]
                }
                n = next((v["n"] for v in per.values() if v), 0)
                cells = " | ".join(_cell(per.get(m)) for m in models)
                lines.append(f"| {label} | {kind} cases | {n} | {cells} |")
        n = next((fam["overall"][m]["n"] for m in models if m in fam["overall"]), 0)
        marked: list[str] = []
        for m in models:
            st = fam["overall"].get(m)
            if not st:
                marked.append("n/a")
                continue
            mark = "pass" if st.get("passes") else "below bar"
            marked.append(f"{st['accuracy']:.3f} ({mark})")
        lines.append(f"| {label} | all, bar {bar:.2f} | {n} | " + " | ".join(marked) + " |")
    return "\n".join(lines) + "\n"


def write_readme_table(readme: Path, text: str) -> bool:
    if not readme.is_file():
        return False
    body = readme.read_text(encoding="utf-8")
    if START not in body or END not in body:
        return False
    new = re.sub(
        re.escape(START) + r".*?" + re.escape(END),
        lambda _m: f"{START}\n{text}{END}",
        body,
        flags=re.S,
    )
    readme.write_text(new, encoding="utf-8")
    return True


def report(layout: Layout, registry: Registry) -> dict[str, Any]:
    summary = summarise(layout, registry)
    text = table(summary)
    (layout.results / "table.md").write_text(text, encoding="utf-8")
    write_readme_table(layout.readme, text)
    return summary
