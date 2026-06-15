"""Minimal localhost proxy: OpenAI-style /v1/chat/completions -> ByteDance AIDP (Azure protocol).

graphify's openai-compat backend speaks plain OpenAI; the AIDP gateway only speaks
the Azure protocol (azure_endpoint + api_version + api-key header). This proxy bridges
the two so graphify can use the GPT-5.1 endpoint unmodified.

Run with the project venv python (needs `openai`):
    .venv/bin/python scripts/aidp_proxy.py
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from openai import AzureOpenAI

API_KEY = os.environ["AIDP_API_KEY"]
BASE_URL = "https://aidp.bytedance.net/api/modelhub/online/v2/crawl"
API_VERSION = "2024-02-01"
DEFAULT_HEADERS = {"X-TT-LOGID": "graphify-extract"}
HOST, PORT = "127.0.0.1", 8765

_client = AzureOpenAI(
    api_key=API_KEY,
    api_version=API_VERSION,
    azure_endpoint=BASE_URL,
    default_headers=DEFAULT_HEADERS,
)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # quieter logs
        sys.stderr.write("[aidp-proxy] " + (args[0] % args[1:]) + "\n")

    def _send(self, code: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if not self.path.endswith("/chat/completions"):
            self._send(404, {"error": {"message": f"unknown path {self.path}"}})
            return
        length = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError as exc:
            self._send(400, {"error": {"message": f"bad json: {exc}"}})
            return

        kwargs = {
            "model": req.get("model"),
            "messages": req.get("messages", []),
        }
        # gpt-5.1 (reasoning) accepts only the default temperature; drop whatever
        # graphify sends. Pass through the output-token cap under both spellings.
        if "max_completion_tokens" in req:
            kwargs["max_completion_tokens"] = req["max_completion_tokens"]
        elif "max_tokens" in req:
            kwargs["max_completion_tokens"] = req["max_tokens"]

        try:
            resp = _client.chat.completions.create(**kwargs)
        except Exception as exc:  # surface upstream error to the client
            self._send(500, {"error": {"message": f"{type(exc).__name__}: {exc}"}})
            return
        self._send(200, json.loads(resp.model_dump_json()))


if __name__ == "__main__":
    print(f"[aidp-proxy] listening on http://{HOST}:{PORT} -> {BASE_URL}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
