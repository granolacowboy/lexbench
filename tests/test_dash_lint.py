"""Dash lint: no em dash, en dash or figure dash in any visible string LexBench authors.

Scanned: every text file in the repository. Not scanned: version-control and tool
directories, the third-party LegalBench records and prompts (materialised by
`lexbench build`, excluded from version control), and model output (results/raw and the
graded per-case records), which are data rather than LexBench text.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import REPO

DASHES = {"\u2012": "figure dash", "\u2013": "en dash", "\u2014": "em dash"}
SKIP_DIRS = {
    ".git",
    ".venv",
    ".lexbench-cache",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "__pycache__",
}
SKIP_PREFIXES = ("data/legalbench/prompts/", "results/raw/")
SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".jsonl", ".toml", ".txt", ".cfg", ""}


def _skipped(rel: str) -> bool:
    if rel.startswith(SKIP_PREFIXES):
        return True
    if rel.startswith("data/legalbench/") and rel.endswith(".jsonl"):
        return True
    parts = rel.split("/")
    return len(parts) == 3 and parts[0] == "results" and rel.endswith(".jsonl")


def scan(root: Path) -> list[str]:
    hits = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if (
            not path.is_file()
            or SKIP_DIRS & set(rel.split("/"))
            or _skipped(rel)
            or path.suffix not in SUFFIXES
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), start=1):
            for ch, name in DASHES.items():
                if ch in line:
                    hits.append(f"{rel}:{n}: {name}")
    return hits


def test_no_dashes_in_repository() -> None:
    assert scan(REPO) == []


def test_lint_detects_a_dash(tmp_path: Path) -> None:
    (tmp_path / "x.md").write_text("a \u2014 b\n", encoding="utf-8")
    assert scan(tmp_path) == ["x.md:1: em dash"]
