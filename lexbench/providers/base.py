"""The provider interface. Every adapter implements the same five operations.

estimate(requests)        token and USD estimate for a list of requests; never calls a model
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
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from lexbench.records import Request, Response
from lexbench.registry import ModelEntry

CHARS_PER_TOKEN = 3.0
MESSAGE_OVERHEAD_TOKENS = 16


class ProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class Estimate:
    requests: int
    input_tokens: int
    output_tokens: int
    usd: float


@dataclass(frozen=True)
class BatchStatus:
    batch_id: str
    status: str  # in_progress, ended, failed
    counts: dict[str, int] = field(default_factory=dict)


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
        out = sum(min(r.max_tokens, self.entry.max_tokens) for r in requests)
        usd = self.entry.pricing.usd(inp, out, batch=self.entry.batch)
        return Estimate(len(requests), inp, out, round(usd, 4))

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
