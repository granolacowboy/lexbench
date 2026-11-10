"""Mock adapter: deterministic responses for tests and dry runs. Never calls a network.

options.mode selects the behaviour:
  oracle    return the reference answer the family attached to the request (default)
  constant  return options.text for every request
  hash      return one of the request's answer options, chosen by a hash of the prompt
Batches are simulated: submit stores the requests under the cache directory and poll
reports them as ended at once.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from lexbench.providers.base import BatchStatus, Provider, ProviderError
from lexbench.records import Request, Response, read_jsonl, write_jsonl


class MockProvider(Provider):
    name = "mock"

    def list_models(self) -> list[str]:
        return [self.entry.model]

    def _answer(self, req: Request) -> str:
        mode = self.entry.options.get("mode", "oracle")
        if mode == "constant":
            return str(self.entry.options.get("text", ""))
        if mode == "hash":
            choices = [str(c) for c in req.meta.get("choices", [])] or ["unknown"]
            digest = int(hashlib.sha256(req.prompt.encode("utf-8")).hexdigest(), 16)
            return choices[digest % len(choices)]
        return str(req.meta.get("reference", ""))

    def _respond(self, req: Request) -> Response:
        text = self._answer(req)
        return Response(
            req.custom_id, text, self.estimate([req]).input_tokens, max(1, len(text) // 4)
        )

    def _path(self, batch_id: str) -> Path:
        return self.cache_dir / "mock" / f"{batch_id}.jsonl"

    def run_sync(self, requests: Sequence[Request]) -> list[Response]:
        return [self._respond(r) for r in requests]

    def submit_batch(self, requests: Sequence[Request]) -> str:
        ids = json.dumps([self.entry.fingerprint(), *(r.custom_id for r in requests)]).encode(
            "utf-8"
        )
        batch_id = "mockbatch_" + hashlib.sha256(ids).hexdigest()[:16]
        rows = [
            {
                "custom_id": r.custom_id,
                "system": r.system,
                "prompt": r.prompt,
                "max_tokens": r.max_tokens,
                "meta": r.meta,
            }
            for r in requests
        ]
        write_jsonl(self._path(batch_id), rows)
        return batch_id

    def poll_batch(self, batch_id: str) -> BatchStatus:
        path = self._path(batch_id)
        if not path.is_file():
            raise ProviderError(f"unknown mock batch {batch_id}")
        n = len(read_jsonl(path))
        return BatchStatus(batch_id, "ended", {"processing": 0, "succeeded": n, "errored": 0})

    def fetch_batch(self, batch_id: str) -> list[Response]:
        path = self._path(batch_id)
        if not path.is_file():
            raise ProviderError(f"unknown mock batch {batch_id}")
        reqs = [
            Request(r["custom_id"], r["system"], r["prompt"], r["max_tokens"], r["meta"])
            for r in read_jsonl(path)
        ]
        return [self._respond(r) for r in reqs]
