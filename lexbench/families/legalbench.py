"""LegalBench family: a licensed subset of nguha/legalbench (Guha et al. 2023).

For each task in sources/legalbench/tasks.yaml the build reads the task README from
HazyResearch/legalbench at a pinned commit, refuses the task unless its license is CC BY
4.0 or more permissive, fetches the upstream base prompt (whose in-context examples are
upstream's few-shot demonstrations from the train split), loads the test split from the
Hugging Face dataset at a pinned revision, and keeps a fixed random sample of at most
sample_size examples (seeded per task) when the split is larger. Cases listed under
`exclude` in tasks.yaml are then dropped from the sample, and recorded with their reason in
data/legalbench/LICENSES.md and data/MANIFEST.json.
"""

from __future__ import annotations

import random
import re
import textwrap
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import httpx
import yaml

from lexbench.families import case_record
from lexbench.records import utc_now

FAMILY = "legalbench"
MAX_TOKENS = 24
SYSTEM = (
    "You are answering a legal reasoning benchmark question. Complete the final answer in "
    "the same format as the examples, with the label only and no explanation."
)
GITHUB_API = "https://api.github.com/repos/{repo}/commits/main"
HF_API = "https://huggingface.co/api/datasets/{dataset}"
RAW = "https://raw.githubusercontent.com/{repo}/{sha}/tasks/{task}/{name}"
PERMITTED = {
    "cc by 4.0": "CC BY 4.0",
    "cc0": "CC0 1.0",
    "cc0 1.0": "CC0 1.0",
    "mit": "MIT",
    "apache 2.0": "Apache 2.0",
    "public domain": "Public domain",
}
_LICENSE = re.compile(r"\*\*License\*\*\s*:\s*\[?([^\]\n(]+)", re.IGNORECASE)
_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")


@dataclass(frozen=True)
class LicenseEvidence:
    task: str
    license: str
    permitted: bool
    url: str
    fetched_at: str
    line: str


def parse_license(readme: str) -> tuple[str, str]:
    """(normalised license, the README line it was read from); ('', '') when absent."""
    match = _LICENSE.search(readme)
    if not match:
        return "", ""
    raw = re.sub(r"\s+", " ", match.group(1)).strip().lower().replace("-", " ")
    line = readme[match.start() :].splitlines()[0].strip()
    return raw, line


def permitted_name(raw: str) -> str | None:
    return PERMITTED.get(raw.strip())


def render(template: str, row: dict[str, Any]) -> str:
    missing = [k for k in _PLACEHOLDER.findall(template) if k not in row]
    if missing:
        raise ValueError(f"legalbench: prompt placeholders without a column: {missing}")
    return _PLACEHOLDER.sub(lambda m: str(row[m.group(1)]), template)


def sample_indices(n: int, size: int, seed: int, task: str) -> list[int]:
    if n <= size:
        return list(range(n))
    return sorted(random.Random(f"{seed}:{task}").sample(range(n), size))


def apply_exclusions(
    rows: list[dict[str, Any]], excluded: set[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Rows without the excluded case ids, and the ids that were dropped."""
    kept = [r for r in rows if r["id"] not in excluded]
    dropped = [str(r["id"]) for r in rows if r["id"] in excluded]
    return kept, dropped


_ROW = re.compile(
    r"^\| (?P<task>[^|]+?) \| [^|]*? \| (?P<lic>[^|]+?) \| [^|]+? \| "
    r"(?P<url>\S+) \| (?P<at>[^|]+?) \|$"
)


def keep_fetch_times(evidence: list[LicenseEvidence], previous: str) -> list[LicenseEvidence]:
    """Evidence with the fetch time already recorded in a previous LICENSES.md, for every
    task whose license and evidence URL are unchanged; other tasks keep the new time."""
    seen: dict[tuple[str, str, str], str] = {}
    for line in previous.splitlines():
        m = _ROW.match(line.strip())
        if m:
            seen[(m["task"], m["lic"], m["url"])] = m["at"]
    return [
        replace(e, fetched_at=seen.get((e.task, e.license, e.url), e.fetched_at)) for e in evidence
    ]


def build(sources: Path, data_dir: Path, sample_size: int | None = None) -> dict[str, Any]:
    """Fetch, verify and materialise the subset. Returns rows per task and provenance."""
    import datasets  # imported here: slow to import and only needed for this family

    cfg = yaml.safe_load((sources / "legalbench" / "tasks.yaml").read_text(encoding="utf-8"))
    size = int(sample_size or cfg["sample_size"])
    seed = int(cfg["seed"])
    reasons = {str(e["id"]): " ".join(str(e["reason"]).split()) for e in cfg.get("exclude", [])}
    excluded: list[str] = []
    with httpx.Client(timeout=60.0, follow_redirects=True) as http:
        gh_sha = (
            cfg.get("upstream_commit")
            or http.get(GITHUB_API.format(repo=cfg["upstream"])).raise_for_status().json()["sha"]
        )
        hf_sha = (
            cfg.get("dataset_revision")
            or http.get(HF_API.format(dataset=cfg["dataset"])).raise_for_status().json()["sha"]
        )
        evidence: list[LicenseEvidence] = []
        rows: dict[str, list[dict[str, Any]]] = {}
        prompts_dir = data_dir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        for spec in cfg["tasks"]:
            task = spec["task"]
            url = RAW.format(repo=cfg["upstream"], sha=gh_sha, task=task, name="README.md")
            readme = http.get(url).raise_for_status().text
            raw, line = parse_license(readme)
            name = permitted_name(raw)
            evidence.append(
                LicenseEvidence(
                    task, name or raw or "not stated", name is not None, url, utc_now(), line
                )
            )
            if name is None:
                continue
            purl = RAW.format(repo=cfg["upstream"], sha=gh_sha, task=task, name="base_prompt.txt")
            template = http.get(purl).raise_for_status().text
            (prompts_dir / f"{task}.txt").write_text(template, encoding="utf-8")
            ds = datasets.load_dataset(cfg["dataset"], task, revision=hf_sha)
            test = ds["test"]
            labels = sorted({str(a) for a in list(ds["train"]["answer"]) + list(test["answer"])})
            out = []
            for i in sample_indices(len(test), size, seed, task):
                row = dict(test[i])
                answer = str(row["answer"])
                out.append(
                    case_record(
                        id=f"lb-{spec['short']}-{int(row['index']):04d}",
                        family=FAMILY,
                        group=task,
                        system=SYSTEM,
                        prompt=render(template, row).rstrip(),
                        max_tokens=MAX_TOKENS,
                        expected={"label": answer, "labels": labels},
                        meta={"reference": answer, "choices": labels},
                    )
                )
            out, dropped = apply_exclusions(out, set(reasons))
            excluded += dropped
            rows[task] = out
    return {
        "rows": rows,
        "evidence": evidence,
        "provenance": {
            "dataset": cfg["dataset"],
            "dataset_revision": hf_sha,
            "upstream": cfg["upstream"],
            "upstream_commit": gh_sha,
            "sample_size": size,
            "seed": seed,
            "excluded": sorted(excluded),
        },
        "exclusion_reasons": {i: reasons[i] for i in sorted(excluded)},
        "reasoning_types": {s["task"]: s["reasoning_type"] for s in cfg["tasks"]},
    }


def licenses_markdown(
    evidence: list[LicenseEvidence],
    provenance: dict[str, Any],
    reasoning: dict[str, str],
    exclusion_reasons: dict[str, str] | None = None,
) -> str:
    head = [
        "# LegalBench task licenses",
        "",
        "LegalBench tasks carry individual licenses. Each license below was read from the task",
        "README in the upstream repository at the pinned commit by `lexbench build`. Only tasks",
        "licensed CC BY 4.0 or more permissively are included. Every build reads each license",
        "again; the time shown is when the evidence shown was first recorded, and it is renewed",
        "when the license or URL changes or when the build is run with `--refresh`.",
        "",
        f"- Upstream repository: https://github.com/{provenance['upstream']}, commit "
        f"`{provenance['upstream_commit']}`",
        f"- Dataset: https://huggingface.co/datasets/{provenance['dataset']}, revision "
        f"`{provenance['dataset_revision']}`",
        "- Attribution: LegalBench (Guha et al. 2023), https://arxiv.org/abs/2308.11462",
        "",
        "| Task | Reasoning type | License | Included | Evidence URL | Fetched (UTC) |",
        "|---|---|---|---|---|---|",
    ]
    body = [
        f"| {e.task} | {reasoning.get(e.task, '')} | {e.license} | "
        f"{'yes' if e.permitted else 'no'} | {e.url} | {e.fetched_at} |"
        for e in evidence
    ]
    excluded = list(provenance.get("excluded") or [])
    reasons = exclusion_reasons or {}
    changes = (
        "LexBench renders each sampled test example into the upstream base prompt without "
        f"modification. It keeps a fixed random sample of at most {provenance.get('sample_size')} "
        f"test examples per task (seed {provenance.get('seed')}) and drops the excluded cases "
        "below from that sample."
    )
    tail = [
        "",
        "## Changes made to the upstream material",
        "",
        *textwrap.wrap(changes, width=90),
        "",
        "## Excluded cases",
        "",
    ]
    if excluded:
        for i in excluded:
            reason = reasons.get(i, "excluded in sources/legalbench/tasks.yaml")
            tail += textwrap.wrap(f"- `{i}`: {reason}", width=90, subsequent_indent="  ")
    else:
        tail.append("None.")
    return "\n".join(head + body + tail) + "\n"
