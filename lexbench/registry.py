"""The model registry (models.yaml). Models are configuration, never code.

Each entry under ``models`` is keyed by its name, the key results are filed under. The
schema below is the single definition of an entry; a malformed entry is refused with a
bounded message that names the entry and the first problem found.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import jsonschema
import yaml

MAX_MESSAGE = 240

PRICING_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["input_per_mtok", "output_per_mtok"],
    "additionalProperties": False,
    "properties": {
        "input_per_mtok": {"type": "number", "minimum": 0},
        "output_per_mtok": {"type": "number", "minimum": 0},
        "batch_discount": {"type": "number", "minimum": 0, "maximum": 1},
        "page_name": {"type": "string", "minLength": 1},
    },
}

ENTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["provider", "model", "pricing", "max_tokens", "concurrency", "batch"],
    "additionalProperties": False,
    "properties": {
        "provider": {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
        "model": {"type": "string", "minLength": 1},
        "endpoint": {"type": "string", "pattern": "^https?://"},
        "auth": {"type": "string", "pattern": "^[A-Z][A-Z0-9_]*$"},
        "pricing": PRICING_SCHEMA,
        "max_tokens": {"type": "integer", "minimum": 1, "maximum": 65536},
        "concurrency": {"type": "integer", "minimum": 1, "maximum": 256},
        "rate_limit_rpm": {"type": "integer", "minimum": 1},
        "batch": {"type": "boolean"},
        "options": {"type": "object"},
    },
}

REGISTRY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["schema_version", "models"],
    "additionalProperties": False,
    "properties": {
        "schema_version": {"const": 1},
        "limits": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "spend_cap_usd": {"type": "number", "exclusiveMinimum": 0},
                "max_requests_per_batch": {"type": "integer", "minimum": 1, "maximum": 100000},
            },
        },
        "models": {
            "type": "object",
            "minProperties": 1,
            "propertyNames": {"pattern": "^[a-z0-9][a-z0-9._-]{0,63}$"},
        },
    },
}


class RegistryError(ValueError):
    """A refused registry or entry. The message is bounded to MAX_MESSAGE characters."""

    def __init__(self, message: str) -> None:
        if len(message) > MAX_MESSAGE:
            message = message[: MAX_MESSAGE - 3] + "..."
        super().__init__(message)


@dataclass(frozen=True)
class Pricing:
    input_per_mtok: float
    output_per_mtok: float
    batch_discount: float = 0.0
    page_name: str | None = None

    def usd(self, input_tokens: int, output_tokens: int, batch: bool) -> float:
        factor = (1.0 - self.batch_discount) if batch else 1.0
        cost = (input_tokens * self.input_per_mtok + output_tokens * self.output_per_mtok) / 1e6
        return cost * factor

    @property
    def is_free(self) -> bool:
        return self.input_per_mtok == 0 and self.output_per_mtok == 0


@dataclass(frozen=True)
class ModelEntry:
    name: str
    provider: str
    model: str
    pricing: Pricing
    max_tokens: int
    concurrency: int
    batch: bool
    endpoint: str | None = None
    auth: str | None = None
    rate_limit_rpm: int | None = None
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Registry:
    entries: dict[str, ModelEntry]
    spend_cap_usd: float
    max_requests_per_batch: int

    def get(self, name: str) -> ModelEntry:
        if name not in self.entries:
            known = ", ".join(sorted(self.entries))
            raise RegistryError(f"unknown model entry {name!r}; known entries: {known}")
        return self.entries[name]


def _first_error(schema: dict[str, Any], instance: Any) -> str | None:
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if not errors:
        return None
    err = errors[0]
    where = "/".join(str(p) for p in err.absolute_path) or "(top level)"
    if err.validator in {"additionalProperties", "required"}:
        # These messages name keys only, never values.
        return f"{where}: {err.message}"
    # Never echo the offending value: an auth field may hold a pasted secret.
    return f"{where}: violates {err.validator} {err.validator_value!r}"


def parse_registry(raw: Any, known_providers: set[str] | None = None) -> Registry:
    problem = _first_error(REGISTRY_SCHEMA, raw)
    if problem:
        raise RegistryError(f"models.yaml refused: {problem}")
    entries: dict[str, ModelEntry] = {}
    for name, body in raw["models"].items():
        problem = _first_error(ENTRY_SCHEMA, body)
        if problem:
            raise RegistryError(f"entry {name!r} refused: {problem}")
        if known_providers is not None and body["provider"] not in known_providers:
            raise RegistryError(
                f"entry {name!r} refused: provider {body['provider']!r} is not one of "
                + ", ".join(sorted(known_providers))
            )
        if body["provider"] == "openai_compatible" and "endpoint" not in body:
            raise RegistryError(f"entry {name!r} refused: openai_compatible requires endpoint")
        if body["batch"] and body["provider"] == "openai_compatible":
            raise RegistryError(f"entry {name!r} refused: openai_compatible has no batch mode")
        p = body["pricing"]
        entries[name] = ModelEntry(
            name=name,
            provider=body["provider"],
            model=body["model"],
            pricing=Pricing(
                input_per_mtok=float(p["input_per_mtok"]),
                output_per_mtok=float(p["output_per_mtok"]),
                batch_discount=float(p.get("batch_discount", 0.0)),
                page_name=p.get("page_name"),
            ),
            max_tokens=int(body["max_tokens"]),
            concurrency=int(body["concurrency"]),
            batch=bool(body["batch"]),
            endpoint=body.get("endpoint"),
            auth=body.get("auth"),
            rate_limit_rpm=body.get("rate_limit_rpm"),
            options=dict(body.get("options") or {}),
        )
    limits = raw.get("limits") or {}
    return Registry(
        entries=entries,
        spend_cap_usd=float(limits.get("spend_cap_usd", 60.0)),
        max_requests_per_batch=int(limits.get("max_requests_per_batch", 10000)),
    )


def load_registry(path: Path, known_providers: set[str] | None = None) -> Registry:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RegistryError(f"models.yaml unreadable: {exc}") from exc
    return parse_registry(raw, known_providers)
