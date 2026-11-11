"""Shared record types and JSON helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CUSTOM_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Request:
    """One model request. meta is never sent to a provider; only the mock adapter reads it."""

    custom_id: str
    system: str
    prompt: str
    max_tokens: int
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Response:
    custom_id: str
    text: str | None
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "custom_id": self.custom_id,
            "text": self.text,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "error": self.error,
        }

    @staticmethod
    def from_json(obj: dict[str, Any]) -> Response:
        return Response(
            custom_id=str(obj["custom_id"]),
            text=obj.get("text"),
            input_tokens=int(obj.get("input_tokens") or 0),
            output_tokens=int(obj.get("output_tokens") or 0),
            error=obj.get("error"),
        )


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    """Write through a temporary file and a rename, so that a reader (another process, or
    the heartbeat of a synchronous run) never sees a partly written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunked[T](items: list[T], size: int) -> Iterator[list[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]
