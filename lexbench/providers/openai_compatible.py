"""OpenAI-compatible adapter: chat completions against any base URL, over plain HTTP.

The endpoint is the base URL that serves /chat/completions and /models, for example
http://localhost:8000/v1 for vLLM, http://localhost:11434/v1 for Ollama, or
https://openrouter.ai/api/v1. Authentication, when the entry names an auth variable, is a
bearer token read from that variable. Synchronous only, with bounded concurrency.
"""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

from lexbench.providers.base import Provider, ProviderError, RateLimiter
from lexbench.records import Request, Response

RETRY_STATUS = {408, 409, 429, 500, 502, 503, 504}


class OpenAICompatibleProvider(Provider):
    name = "openai_compatible"

    def _client(self, timeout: float = 120.0) -> httpx.Client:
        if not self.entry.endpoint:
            raise ProviderError("openai_compatible entry has no endpoint")
        headers = {"Content-Type": "application/json"}
        if self.entry.auth:
            key = os.environ.get(self.entry.auth, "")
            if not key:
                raise ProviderError(f"environment variable {self.entry.auth} is EMPTY")
            headers["Authorization"] = f"Bearer {key}"
        return httpx.Client(
            base_url=self.entry.endpoint.rstrip("/") + "/", headers=headers, timeout=timeout
        )

    def list_models(self) -> list[str]:
        with self._client(timeout=10.0) as client:
            resp = client.get("models")
            resp.raise_for_status()
            data = resp.json().get("data", [])
            return [str(m.get("id")) for m in data if isinstance(m, dict)]

    def _body(self, req: Request) -> dict[str, Any]:
        messages = []
        if req.system:
            messages.append({"role": "system", "content": req.system})
        messages.append({"role": "user", "content": req.prompt})
        body: dict[str, Any] = {
            "model": self.entry.model,
            "messages": messages,
            "max_tokens": min(req.max_tokens, self.entry.max_tokens),
            "temperature": 0,
        }
        body.update(self.entry.options.get("params", {}))
        return body

    def run_sync(self, requests: Sequence[Request]) -> list[Response]:
        limiter = RateLimiter(self.entry.rate_limit_rpm)
        attempts = int(self.entry.options.get("retries", 3)) + 1

        with self._client() as client:

            def one(req: Request) -> Response:
                last = "no attempt"
                for attempt in range(attempts):
                    limiter.wait()
                    try:
                        resp = client.post("chat/completions", json=self._body(req))
                    except httpx.HTTPError as exc:
                        last = type(exc).__name__
                    else:
                        if resp.status_code == 200:
                            return self._parse(req.custom_id, resp)
                        last = f"HTTP {resp.status_code}"
                        if resp.status_code not in RETRY_STATUS:
                            break
                    if attempt + 1 < attempts:
                        time.sleep(min(2**attempt * 0.5, 8.0))
                return Response(req.custom_id, None, error=last)

            with ThreadPoolExecutor(max_workers=self.entry.concurrency) as pool:
                return list(pool.map(one, requests))

    @staticmethod
    def _parse(custom_id: str, resp: httpx.Response) -> Response:
        try:
            obj = resp.json()
            text = obj["choices"][0]["message"]["content"]
            usage = obj.get("usage") or {}
        except (ValueError, KeyError, IndexError, TypeError):
            return Response(custom_id, None, error="malformed completion")
        return Response(
            custom_id,
            text if isinstance(text, str) else None,
            int(usage.get("prompt_tokens") or 0),
            int(usage.get("completion_tokens") or 0),
        )
