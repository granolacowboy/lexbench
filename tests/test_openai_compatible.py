"""The openai_compatible adapter against a local fake server."""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, ClassVar

import pytest

from lexbench.providers import ProviderError, make_provider
from lexbench.records import Request
from lexbench.registry import parse_registry


class FakeServer(BaseHTTPRequestHandler):
    seen: ClassVar[list[dict[str, Any]]] = []
    auth: ClassVar[list[str]] = []
    fail_once: ClassVar[set[str]] = set()

    def log_message(self, *_args: Any) -> None:
        return

    def _send(self, code: int, body: Any) -> None:
        data = (body if isinstance(body, str) else json.dumps(body)).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        if self.path == "/v1/models":
            self._send(200, {"object": "list", "data": [{"id": "local-model"}]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeServer.seen.append(body)
        FakeServer.auth.append(self.headers.get("Authorization", ""))
        prompt = body["messages"][-1]["content"]
        if prompt == "retry" and "retry" not in FakeServer.fail_once:
            FakeServer.fail_once.add("retry")
            self._send(503, {"error": "busy"})
            return
        if prompt == "malformed":
            self._send(200, {"choices": []})
            return
        if prompt == "bad request":
            self._send(400, {"error": "bad"})
            return
        self._send(
            200,
            {
                "choices": [{"message": {"role": "assistant", "content": f"echo:{prompt}"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 2},
            },
        )


@pytest.fixture()
def server() -> Iterator[str]:
    FakeServer.seen.clear()
    FakeServer.auth.clear()
    FakeServer.fail_once.clear()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeServer)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/v1"
    httpd.shutdown()


def _provider(endpoint: str, tmp_path: Path, auth: str | None = None) -> Any:
    entry: dict[str, Any] = {
        "provider": "openai_compatible",
        "model": "local-model",
        "endpoint": endpoint,
        "pricing": {"input_per_mtok": 0, "output_per_mtok": 0},
        "max_tokens": 64,
        "concurrency": 3,
        "batch": False,
        "options": {"retries": 2},
    }
    if auth:
        entry["auth"] = auth
    reg = parse_registry({"schema_version": 1, "models": {"local": entry}})
    return make_provider(reg.get("local"), tmp_path)


def test_sync_run_and_listing(server: str, tmp_path: Path) -> None:
    provider = _provider(server, tmp_path)
    assert provider.list_models() == ["local-model"]
    reqs = [Request(f"c{i}", "Answer briefly.", f"q{i}", max_tokens=500) for i in range(5)]
    out = provider.run_sync(reqs)
    assert [r.text for r in out] == [f"echo:q{i}" for i in range(5)]
    assert all(r.input_tokens == 7 and r.output_tokens == 2 for r in out)
    body = FakeServer.seen[0]
    assert body["max_tokens"] == 64 and body["model"] == "local-model"
    assert body["messages"][0] == {"role": "system", "content": "Answer briefly."}


def test_retry_malformed_and_client_error(server: str, tmp_path: Path) -> None:
    provider = _provider(server, tmp_path)
    out = provider.run_sync(
        [
            Request("a", "", "retry", 8),
            Request("b", "", "malformed", 8),
            Request("c", "", "bad request", 8),
        ]
    )
    assert out[0].text == "echo:retry" and out[0].error is None
    assert out[1].text is None and out[1].error == "malformed completion"
    assert out[2].error == "HTTP 400"


def test_bearer_token_from_named_variable(
    server: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LEXBENCH_TEST_TOKEN", "token-value")
    provider = _provider(server, tmp_path, auth="LEXBENCH_TEST_TOKEN")
    provider.run_sync([Request("a", "", "q", 8)])
    assert FakeServer.auth[-1] == "Bearer token-value"
    monkeypatch.delenv("LEXBENCH_TEST_TOKEN")
    with pytest.raises(ProviderError, match="EMPTY"):
        provider.run_sync([Request("a", "", "q", 8)])


def test_no_batch_mode(server: str, tmp_path: Path) -> None:
    with pytest.raises(ProviderError, match="no batch mode"):
        _provider(server, tmp_path).submit_batch([Request("a", "", "q", 8)])
