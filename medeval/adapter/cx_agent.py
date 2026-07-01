"""cx-agent 测试路由 Adapter。

调用 cx-agent 本地 ``/api/test/chat/send`` SSE 接口：绕过登录，但仍走真实
agentLoop、工具、DB session 与多轮上下文。cx-agent 自己维护历史，所以本 adapter
只发送当前最新 user turn，并用 mme session_id 映射 cx-agent sessionId 续聊。
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .base import BaseAdapter, ChatRequest, ChatResponse
from .registry import register_adapter


CX_AGENT_CHAT_ENDPOINT = "/api/test/chat/send"


def _json_or_text(data: str) -> Any:
    if not data:
        return ""
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return data


def _parse_sse(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    event = "message"
    data_lines: list[str] = []

    def flush() -> None:
        nonlocal event, data_lines
        if not data_lines and event == "message":
            return
        data = "\n".join(data_lines)
        events.append({"event": event, "data": _json_or_text(data)})
        event = "message"
        data_lines = []

    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r")
        if line == "":
            flush()
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].lstrip())

    flush()
    return events


def _extract_delta(data: Any) -> str:
    if isinstance(data, dict):
        value = data.get("content", data.get("text", ""))
        return value if isinstance(value, str) else ""
    return data if isinstance(data, str) else ""


def _extract_error(data: Any) -> str:
    if isinstance(data, dict):
        message = data.get("message") or data.get("error")
        if isinstance(message, str) and message:
            return message
    if isinstance(data, str) and data:
        return data
    return "cx-agent emitted error event"


def _usage_from_message_end(data: Any) -> dict[str, int]:
    if not isinstance(data, dict):
        return {}

    def as_int(key: str) -> int:
        value = data.get(key)
        try:
            return int(value) if value is not None else 0
        except (TypeError, ValueError):
            return 0

    prompt = as_int("inputTokens")
    completion = as_int("outputTokens")
    total = prompt + completion
    return (
        {
            "prompt_tokens": prompt,
            "completion_tokens": completion,
            "total_tokens": total,
        }
        if total
        else {}
    )


@register_adapter("cx_agent", config_key="cx_agent")
class CxAgentAdapter(BaseAdapter):
    name = "cx_agent"

    def __init__(
        self,
        base_url: str = "http://localhost:3000",
        test_token_env: str = "CX_AGENT_TEST_TOKEN",
        test_token: str = "",
        timeout_s: float = 120.0,
    ):
        token = test_token or os.environ.get(test_token_env, "")
        if not token:
            raise RuntimeError(
                f"cx_agent adapter requires test token; set {test_token_env} "
                "or adapter.cx_agent.test_token"
            )
        self.base_url = base_url.rstrip("/")
        self._test_token = token
        self._client = httpx.AsyncClient(timeout=timeout_s)
        self._sessions: dict[str, str] = {}

    async def chat(self, req: ChatRequest) -> ChatResponse:
        latest = req.messages[-1] if req.messages else {}
        if latest.get("role") != "user":
            return ChatResponse(reply="", error="cx_agent adapter requires latest user turn")

        content = str(latest.get("content") or "")
        if not content.strip():
            return ChatResponse(reply="", error="cx_agent adapter requires non-empty user content")

        cx_session_id = self._sessions.get(req.session_id)
        if cx_session_id is None and len(req.messages) > 1:
            return ChatResponse(
                reply="",
                error=(
                    "cx_agent adapter does not support preset history before cx-agent "
                    "session exists"
                ),
            )

        body = {"content": content}
        if cx_session_id:
            body["sessionId"] = cx_session_id

        try:
            resp = await self._client.post(
                self.base_url + CX_AGENT_CHAT_ENDPOINT,
                headers={"X-Test-Token": self._test_token},
                json=body,
            )
            resp.raise_for_status()
            events = _parse_sse(resp.text)
        except Exception as e:  # noqa: BLE001 - adapter failure must be data, not raise
            return ChatResponse(reply="", error=f"cx_agent error: {e}")

        if not events:
            return ChatResponse(reply="", error="cx_agent error: empty SSE response")

        reply_parts: list[str] = []
        raw_events: list[dict[str, Any]] = []
        saw_message_end = False
        usage: dict[str, int] = {}
        error: str | None = None

        for item in events:
            event = item["event"]
            data = item["data"]
            raw_events.append({"event": event, "data": data})
            if event == "session" and isinstance(data, dict):
                session_id = data.get("sessionId")
                if isinstance(session_id, str) and session_id:
                    cx_session_id = session_id
                    self._sessions[req.session_id] = session_id
            elif event == "text_delta":
                reply_parts.append(_extract_delta(data))
            elif event == "message_end":
                saw_message_end = True
                usage = _usage_from_message_end(data)
            elif event == "error":
                error = _extract_error(data)

        raw: dict[str, Any] = {
            "events": raw_events,
            "cx_session_id": cx_session_id,
        }
        if usage:
            raw["usage"] = usage

        if error:
            return ChatResponse(reply="", raw=raw, error=error)
        if not saw_message_end:
            return ChatResponse(reply="", raw=raw, error="cx_agent error: missing message_end")
        return ChatResponse(reply="".join(reply_parts), raw=raw)

    async def close(self) -> None:
        await self._client.aclose()
