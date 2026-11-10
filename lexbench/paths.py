"""Repository layout. Every path is resolved against one root so that tests can use a copy."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

FAMILIES: tuple[str, ...] = ("legalbench", "fragments", "routing")


def default_root() -> Path:
    """The root is LEXBENCH_ROOT when set, else the nearest parent holding models.yaml."""
    env = os.environ.get("LEXBENCH_ROOT")
    if env:
        return Path(env).resolve()
    here = Path.cwd().resolve()
    for candidate in (here, *here.parents):
        if (candidate / "models.yaml").is_file():
            return candidate
    return here


@dataclass(frozen=True)
class Layout:
    root: Path

    @property
    def models_yaml(self) -> Path:
        return self.root / "models.yaml"

    @property
    def sources(self) -> Path:
        return self.root / "sources"

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def manifest(self) -> Path:
        return self.data / "MANIFEST.json"

    @property
    def results(self) -> Path:
        return self.root / "results"

    @property
    def estimate(self) -> Path:
        return self.results / "estimate.json"

    @property
    def summary(self) -> Path:
        return self.results / "summary.json"

    @property
    def state(self) -> Path:
        return self.root / "state"

    @property
    def batches(self) -> Path:
        return self.state / "batches.json"

    @property
    def runs(self) -> Path:
        return self.state / "runs.json"

    @property
    def cache(self) -> Path:
        return self.root / ".lexbench-cache"

    @property
    def readme(self) -> Path:
        return self.root / "README.md"

    def family_dir(self, family: str) -> Path:
        return self.data / family

    def raw_path(self, family: str, model: str, submission_id: str) -> Path:
        return self.results / "raw" / family / model / f"{submission_id}.jsonl"

    def graded_path(self, family: str, model: str) -> Path:
        return self.results / family / f"{model}.jsonl"
