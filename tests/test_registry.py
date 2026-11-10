"""Registry validation: malformed entries are refused with a bounded message."""

from __future__ import annotations

import copy
from typing import Any

import pytest

from lexbench.providers import PROVIDERS
from lexbench.registry import MAX_MESSAGE, RegistryError, load_registry, parse_registry
from tests.conftest import REGISTRY, REPO


def _with(entry_patch: dict[str, Any], drop: str | None = None) -> dict[str, Any]:
    raw = copy.deepcopy(REGISTRY)
    entry = raw["models"]["mock"]
    entry.update(entry_patch)
    if drop:
        del entry[drop]
    return raw


def test_shipped_registry_is_valid() -> None:
    reg = load_registry(REPO / "models.yaml", set(PROVIDERS))
    assert {"claude-opus-5-5", "claude-sonnet-5-5", "mock"} <= set(reg.entries)
    assert any(n.startswith("claude-haiku") for n in reg.entries)
    assert reg.spend_cap_usd == 60.0
    assert reg.max_requests_per_batch == 10000


@pytest.mark.parametrize(
    "raw, fragment",
    [
        (_with({}, drop="pricing"), "pricing"),
        (_with({"pricing": {"input_per_mtok": -1, "output_per_mtok": 0}}), "pricing"),
        (_with({"max_tokens": "many"}), "max_tokens"),
        (_with({"auth": "pasted-secret-value"}), "auth"),
        (_with({"provider": "telepathy"}), "telepathy"),
        (_with({"unexpected": "x" * 5000}), "unexpected"),
        (_with({"provider": "openai_compatible"}), "endpoint"),
    ],
)
def test_malformed_entry_refused(raw: dict[str, Any], fragment: str) -> None:
    with pytest.raises(RegistryError) as info:
        parse_registry(raw, set(PROVIDERS))
    message = str(info.value)
    assert len(message) <= MAX_MESSAGE
    assert "mock" in message and fragment in message


def test_refusal_never_echoes_the_value() -> None:
    with pytest.raises(RegistryError) as info:
        parse_registry(_with({"auth": "pasted-secret-value"}), set(PROVIDERS))
    assert "pasted-secret" not in str(info.value)


def test_batch_refused_for_openai_compatible() -> None:
    raw = _with({"provider": "openai_compatible", "endpoint": "http://localhost:1/v1"})
    with pytest.raises(RegistryError, match="no batch mode"):
        parse_registry(raw, set(PROVIDERS))


def test_top_level_refused() -> None:
    with pytest.raises(RegistryError):
        parse_registry({"schema_version": 2, "models": {}}, set(PROVIDERS))
    with pytest.raises(RegistryError):
        parse_registry("not a mapping", set(PROVIDERS))
