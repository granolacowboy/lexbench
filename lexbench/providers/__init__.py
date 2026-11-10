"""Provider adapters. Adding a provider is one Provider subclass added to PROVIDERS."""

from __future__ import annotations

from pathlib import Path

from lexbench.providers.anthropic_provider import AnthropicProvider
from lexbench.providers.base import BatchStatus, Estimate, Provider, ProviderError
from lexbench.providers.mock import MockProvider
from lexbench.providers.openai_compatible import OpenAICompatibleProvider
from lexbench.registry import ModelEntry

PROVIDERS: dict[str, type[Provider]] = {
    AnthropicProvider.name: AnthropicProvider,
    OpenAICompatibleProvider.name: OpenAICompatibleProvider,
    MockProvider.name: MockProvider,
}


def make_provider(entry: ModelEntry, cache_dir: Path) -> Provider:
    try:
        cls = PROVIDERS[entry.provider]
    except KeyError as exc:
        raise ProviderError(f"no adapter named {entry.provider!r}") from exc
    return cls(entry, cache_dir)


__all__ = [
    "PROVIDERS",
    "BatchStatus",
    "Estimate",
    "Provider",
    "ProviderError",
    "make_provider",
]
