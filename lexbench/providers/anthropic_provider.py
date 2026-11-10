"""Anthropic adapter: the Messages API for synchronous runs, Message Batches when batch is true."""

from __future__ import annotations

import os
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import anthropic

from lexbench.providers.base import BatchStatus, Provider, ProviderError, RateLimiter
from lexbench.records import Request, Response


class AnthropicProvider(Provider):
    name = "anthropic"

    def _client(self) -> anthropic.Anthropic:
        var = self.entry.auth or "ANTHROPIC_API_KEY"
        key = os.environ.get(var, "")
        if not key:
            raise ProviderError(f"environment variable {var} is EMPTY")
        if self.entry.endpoint:
            return anthropic.Anthropic(api_key=key, max_retries=4, base_url=self.entry.endpoint)
        return anthropic.Anthropic(api_key=key, max_retries=4)

    def _params(self, req: Request) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.entry.model,
            "max_tokens": self.entry.output_bound(req.max_tokens),
            "messages": [{"role": "user", "content": req.prompt}],
        }
        if req.system:
            params["system"] = req.system
        params.update(self.entry.options.get("params", {}))
        return params

    @staticmethod
    def _text(content: Any) -> str:
        return "".join(
            str(getattr(block, "text", ""))
            for block in content
            if getattr(block, "type", "") == "text"
        )

    def list_models(self) -> list[str]:
        client = self._client()
        return [str(m.id) for m in client.models.list(limit=1000)]

    def run_sync(self, requests: Sequence[Request]) -> list[Response]:
        client = self._client()
        limiter = RateLimiter(self.entry.rate_limit_rpm)

        def one(req: Request) -> Response:
            limiter.wait()
            try:
                msg = client.messages.create(**self._params(req))
            except anthropic.APIError as exc:
                return Response(req.custom_id, None, error=type(exc).__name__)
            return Response(
                req.custom_id,
                self._text(msg.content),
                msg.usage.input_tokens,
                msg.usage.output_tokens,
            )

        with ThreadPoolExecutor(max_workers=self.entry.concurrency) as pool:
            return list(pool.map(one, requests))

    def submit_batch(self, requests: Sequence[Request]) -> str:
        client = self._client()
        body: list[Any] = [{"custom_id": r.custom_id, "params": self._params(r)} for r in requests]
        batch = client.messages.batches.create(requests=body)
        return str(batch.id)

    def poll_batch(self, batch_id: str) -> BatchStatus:
        batch = self._client().messages.batches.retrieve(batch_id)
        rc = batch.request_counts
        counts = {
            "processing": rc.processing,
            "succeeded": rc.succeeded,
            "errored": rc.errored,
            "canceled": rc.canceled,
            "expired": rc.expired,
        }
        status = "ended" if batch.processing_status == "ended" else "in_progress"
        return BatchStatus(batch_id, status, counts)

    def fetch_batch(self, batch_id: str) -> list[Response]:
        out: list[Response] = []
        # Hold the client for the whole download: the results stream is read lazily, and a
        # client that is garbage collected mid-stream closes the connection.
        client = self._client()
        for item in client.messages.batches.results(batch_id):
            result = item.result
            if result.type == "succeeded":
                msg = result.message
                out.append(
                    Response(
                        item.custom_id,
                        self._text(msg.content),
                        msg.usage.input_tokens,
                        msg.usage.output_tokens,
                    )
                )
            else:
                out.append(Response(item.custom_id, None, error=str(result.type)))
        return out
