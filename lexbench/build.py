"""`lexbench build`: materialise the three families into data/ with data/MANIFEST.json."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lexbench.families import fragments, legalbench, routing
from lexbench.paths import FAMILIES, Layout
from lexbench.records import read_json, read_jsonl, sha256_file, sha256_text, utc_now, write_json
from lexbench.records import write_jsonl as _write


def _files_entry(layout: Layout, paths: list[Path]) -> dict[str, Any]:
    files = {}
    for p in sorted(paths):
        files[p.relative_to(layout.root).as_posix()] = {
            "count": len(read_jsonl(p)),
            "sha256": sha256_file(p),
        }
    digest = sha256_text("\n".join(f"{k}:{v['sha256']}" for k, v in files.items()))
    return {"count": sum(v["count"] for v in files.values()), "sha256": digest, "files": files}


def _replace_dir(directory: Path, groups: dict[str, list[dict[str, Any]]]) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    for old in directory.glob("*.jsonl"):
        old.unlink()
    paths = []
    for group, rows in groups.items():
        path = directory / f"{group}.jsonl"
        _write(path, rows)
        paths.append(path)
    return paths


def _unchanged(previous: dict[str, Any], entry: dict[str, Any]) -> bool:
    return {k: v for k, v in previous.items() if k != "built_at"} == entry


def build(
    layout: Layout, families: list[str], sample_size: int | None = None, refresh: bool = False
) -> dict[str, Any]:
    """Build the families. Tracked provenance is kept when the built content is unchanged:
    the manifest's built_at and the license fetch times are rewritten only when the content
    or the license evidence changes, or when refresh is true."""
    manifest: dict[str, Any] = read_json(layout.manifest, default=None) or {
        "schema_version": 1,
        "families": {},
    }
    for family in families:
        previous: dict[str, Any] = manifest["families"].get(family, {})
        target = layout.family_dir(family)
        if family == "legalbench":
            result = legalbench.build(layout.sources, target, sample_size)
            if len(result["rows"]) < 6:
                raise RuntimeError(
                    f"STOP: only {len(result['rows'])} LegalBench tasks have a permitted license"
                )
            paths = _replace_dir(target, result["rows"])
            licenses = target / "LICENSES.md"
            evidence = result["evidence"]
            if not refresh and licenses.is_file():
                evidence = legalbench.keep_fetch_times(
                    evidence, licenses.read_text(encoding="utf-8")
                )
            licenses.write_text(
                legalbench.licenses_markdown(
                    evidence,
                    result["provenance"],
                    result["reasoning_types"],
                    result.get("exclusion_reasons"),
                ),
                encoding="utf-8",
            )
            entry = _files_entry(layout, paths)
            entry["provenance"] = result["provenance"]
            entry["tasks"] = {t: result["reasoning_types"][t] for t in result["rows"]}
        elif family == "fragments":
            paths = _replace_dir(target, fragments.build(layout.sources, fragments.SEED))
            entry = _files_entry(layout, paths)
            entry["seed"] = fragments.SEED
            entry["generator"] = "lexbench/families/fragments.py"
        elif family == "routing":
            paths = _replace_dir(target, routing.build(layout.sources))
            entry = _files_entry(layout, paths)
        else:
            raise ValueError(f"unknown family {family!r}; families: {', '.join(FAMILIES)}")
        keep = not refresh and previous.get("built_at") and _unchanged(previous, entry)
        entry["built_at"] = previous["built_at"] if keep else utc_now()
        manifest["families"][family] = entry
    write_json(layout.manifest, manifest)
    return manifest


def load_cases(layout: Layout, family: str) -> list[dict[str, Any]]:
    """All case records of a family, verified against the manifest hashes."""
    manifest = read_json(layout.manifest, default=None)
    if not manifest or family not in manifest.get("families", {}):
        raise RuntimeError(f"family {family!r} is not built; run `lexbench build`")
    rows: list[dict[str, Any]] = []
    for rel, meta in manifest["families"][family]["files"].items():
        path = layout.root / rel
        if not path.is_file() or sha256_file(path) != meta["sha256"]:
            raise RuntimeError(f"{rel} does not match data/MANIFEST.json; rebuild the family")
        rows.extend(read_jsonl(path))
    return rows


def family_sha(layout: Layout, family: str) -> str:
    manifest = read_json(layout.manifest, default=None) or {}
    return str(manifest.get("families", {}).get(family, {}).get("sha256", ""))
