"""Routing family: trigger phrases, the routing suite and written paraphrases to commands."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from graders.routing import check_command_names
from lexbench.families import case_record

FAMILY = "routing"
MAX_TOKENS = 20
SYSTEM = (
    "You route a request from a law firm user to exactly one installed command. "
    "Answer with the command name only."
)


def _key(phrase: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", phrase.lower()).strip()


def build(sources: Path) -> dict[str, list[dict[str, Any]]]:
    imported = yaml.safe_load((sources / "mhsb" / "routing.yaml").read_text(encoding="utf-8"))
    described = yaml.safe_load((sources / "routing" / "commands.yaml").read_text(encoding="utf-8"))
    written = yaml.safe_load((sources / "routing" / "paraphrases.yaml").read_text(encoding="utf-8"))
    descriptions: dict[str, str] = described["commands"]
    names = [c["command"] for c in imported["commands"]]
    check_command_names(names)
    if set(names) != set(descriptions):
        raise ValueError("routing: command descriptions do not match the imported commands")
    if set(written["paraphrases"]) != set(names):
        raise ValueError("routing: paraphrases must cover every command")
    listing = "\n".join(f"- {n}: {descriptions[n]}" for n in names)

    candidates: list[tuple[str, str, str]] = []
    for cmd in imported["commands"]:
        candidates += [(t, cmd["command"], "manifest_trigger") for t in cmd["triggers"]]
    candidates += [(p["phrase"], p["command"], "routing_suite") for p in imported["phrases"]]
    for cmd, phrases in written["paraphrases"].items():
        if len(phrases) < 2:
            raise ValueError(f"routing: fewer than two paraphrases for {cmd}")
        candidates += [(p, cmd, "paraphrase") for p in phrases]

    seen: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for phrase, command, source in candidates:
        key = _key(phrase)
        if key in seen:
            if seen[key] != command:
                raise ValueError(f"routing: phrase {phrase!r} maps to two commands")
            continue
        seen[key] = command
        prompt = (
            f'Installed commands:\n{listing}\n\nRequest: "{phrase}"\n\n'
            "Which command handles this request? Answer with the command name only."
        )
        rows.append(
            case_record(
                id=f"rt-{len(rows) + 1:04d}",
                family=FAMILY,
                group=source,
                system=SYSTEM,
                prompt=prompt,
                max_tokens=MAX_TOKENS,
                expected={"command": command, "phrase": phrase},
                meta={"reference": command, "choices": names},
            )
        )
    return {"cases": rows}
