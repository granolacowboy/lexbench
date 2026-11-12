"""The provider interface. Every adapter implements the same five operations.

estimate(requests)        token and USD estimate for a list of requests; never calls a model;
                          a synchronous entry is priced at retries + 1 attempts per request
run_sync(requests)        run the requests now, with bounded concurrency; returns responses
submit_batch(requests)    submit one asynchronous batch; returns the provider's batch id
poll_batch(batch_id)      report the batch status and request counts
fetch_batch(batch_id)     download the responses of an ended batch

An adapter that has no batch mode raises ProviderError from the three batch operations.
Adding a provider is one subclass registered in lexbench.providers.PROVIDERS.
"""

from __future__ import annotations

import math
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lexbench.records import Request, Response
from lexbench.registry import ModelEntry

CHARS_PER_TOKEN = 3.0
MESSAGE_OVERHEAD_TOKENS = 16
MAX_MESSAGE = 240

# Request fields that bound billed output tokens, at any depth of options.params: the
# output bound itself (Anthropic max_tokens; OpenAI max_tokens or max_completion_tokens;
# max_output_tokens) and a thinking budget (Anthropic thinking.budget_tokens).
OUTPUT_FIELDS = frozenset(
    {"max_tokens", "max_completion_tokens", "max_output_tokens", "budget_tokens"}
)


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class Estimate:
    requests: int
    input_tokens: int
    output_tokens: int
    usd: float
    attempts: int = 1  # attempts priced per request; tokens are those of one attempt


@dataclass(frozen=True)
class BatchStatus:
    batch_id: str
    status: str  # in_progress, ended, failed
    counts: dict[str, int] = field(default_factory=dict)


def _output_fields(value: Any, path: str) -> Iterator[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            where = f"{path}.{key}"
            if key in OUTPUT_FIELDS:
                yield where, item
            yield from _output_fields(item, where)
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from _output_fields(item, f"{path}[{i}]")


def checked_params(entry: ModelEntry, bound: int) -> dict[str, Any]:
    """options.params (or the family's params) after the output-bound rule.

    The estimate prices each request at its output bound. params may lower an output field
    but may not set one above the bound or to a value that is not an integer: such an
    override is refused with a bounded message, so that it can neither raise max_tokens
    above what the estimate priced nor add a thinking budget the estimate did not price.
    """
    params = entry.options.get("params", {})
    if not isinstance(params, dict):
        raise ProviderError(f"entry {entry.name!r}: options.params must be a mapping")
    for where, value in _output_fields(params, "params"):
        if isinstance(value, bool) or not isinstance(value, int) or value > bound:
            shown = value if isinstance(value, int) else type(value).__name__
            message = (
                f"entry {entry.name!r} refused: {where} {shown} exceeds the output bound "
                f"{bound} that the estimate prices; set max_tokens, reasoning_tokens or "
                "family_settings.max_tokens instead"
            )
            raise ProviderError(message[:MAX_MESSAGE])
    return dict(params)


def estimate_tokens(text: str) -> int:
    """A conservative character-based token estimate (three characters per token)."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)


class RateLimiter:
    """Spaces request starts so that at most rpm requests start per minute."""

    def __init__(self, rpm: int | None) -> None:
        self._interval = 60.0 / rpm if rpm else 0.0
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        if not self._interval:
            return
        with self._lock:
            now = time.monotonic()
            start = max(now, self._next)
            self._next = start + self._interval
        delay = start - time.monotonic()
        if delay > 0:
            time.sleep(delay)


class Provider(ABC):
    name: str = ""

    def __init__(self, entry: ModelEntry, cache_dir: Path) -> None:
        self.entry = entry
        self.cache_dir = cache_dir

    def estimate(self, requests: Sequence[Request]) -> Estimate:
        inp = sum(
            estimate_tokens(r.system) + estimate_tokens(r.prompt) + MESSAGE_OVERHEAD_TOKENS
            for r in requests
        )
        bounds = [self.entry.output_bound(r.max_tokens) for r in requests]
        for bound in set(bounds):
            checked_params(self.entry, bound)
        out = sum(bounds)
        attempts = self.entry.billed_attempts()
        usd = self.entry.pricing.usd(inp, out, batch=self.entry.batch) * attempts
        return Estimate(len(requests), inp, out, round(usd, 4), attempts)

    def list_models(self) -> list[str]:
        """Identifiers the provider reports as available; empty when it has no listing."""
        return []

    @abstractmethod
    def run_sync(self, requests: Sequence[Request]) -> list[Response]: ...

    def submit_batch(self, requests: Sequence[Request]) -> str:
        raise ProviderError(f"provider {self.name} has no batch mode")

    def poll_batch(self, batch_id: str) -> BatchStatus:
        raise ProviderError(f"provider {self.name} has no batch mode")

    def fetch_batch(self, batch_id: str) -> list[Response]:
        raise ProviderError(f"provider {self.name} has no batch mode")
