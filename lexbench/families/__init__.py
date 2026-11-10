"""Task families. Each module builds its cases into data/<family>/ as JSON lines.

Every case record has the same shape:
  id          the request id (letters, digits, hyphen and underscore, at most 64 characters)
  family      legalbench, fragments or routing
  group       the task, pack or phrase source the case belongs to
  system      the system prompt
  prompt      the user prompt
  max_tokens  the output bound for the case
  expected    the mapping the family's grader compares the response with
  meta        reference answer and answer options; read only by the mock adapter
"""

from __future__ import annotations

from typing import Any

from lexbench.records import CUSTOM_ID, Request


def case_record(
    *,
    id: str,
    family: str,
    group: str,
    system: str,
    prompt: str,
    max_tokens: int,
    expected: dict[str, Any],
    meta: dict[str, Any],
) -> dict[str, Any]:
    if not CUSTOM_ID.match(id):
        raise ValueError(f"case id {id!r} is not a valid request id")
    return {
        "id": id,
        "family": family,
        "group": group,
        "system": system,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "expected": expected,
        "meta": meta,
    }


def to_request(record: dict[str, Any]) -> Request:
    return Request(
        custom_id=record["id"],
        system=record["system"],
        prompt=record["prompt"],
        max_tokens=int(record["max_tokens"]),
        meta=dict(record.get("meta") or {}),
    )
