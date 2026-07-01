from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from medeval.adapter.base import ChatRequest
from medeval.adapter.cx_agent import CxAgentAdapter


def _sse(*events: tuple[str, dict | str]) -> str:
    chunks: list[str] = []
    for event, data in events:
        payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
        chunks.append(f"event: {event}\ndata: {payload}\n\n")
    return "".join(chunks)


def _adapter_with_transport(handler) -> CxAgentAdapter:
    adapter = CxAgentAdapter(
        base_url="http://cx.local",
        test_token="token-1",
        timeout_s=10,
    )
    adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=10)
    return adapter


def test_cx_agent_adapter_parses_sse_reply_and_session():
    seen: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode()))
        assert request.url == "http://cx.local/api/test/chat/send"
        assert request.headers["x-test-token"] == "token-1"
        return httpx.Response(
            200,
            text=_sse(
                ("session", {"sessionId": "cx-s1"}),
                ("text_delta", {"content": "你好"}),
                ("text_delta", {"text": "，请描述症状"}),
                ("message_end", {"messageId": "m1", "inputTokens": 3, "outputTokens": 5}),
            ),
        )

    adapter = _adapter_with_transport(handler)
    resp = asyncio.run(
        adapter.chat(
            ChatRequest(
                messages=[{"role": "user", "content": "乳房疼痛怎么办"}],
                session_id="mme-s1",
            )
        )
    )

    assert resp.error is None
    assert resp.reply == "你好，请描述症状"
    assert resp.raw["cx_session_id"] == "cx-s1"
    assert resp.raw["usage"] == {
        "prompt_tokens": 3,
        "completion_tokens": 5,
        "total_tokens": 8,
    }
    assert seen == [{"content": "乳房疼痛怎么办"}]
    asyncio.run(adapter.close())


def test_cx_agent_adapter_reuses_cx_session_for_same_mme_session():
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        bodies.append(body)
        cx_session = body.get("sessionId") or "cx-new"
        return httpx.Response(
            200,
            text=_sse(
                ("session", {"sessionId": cx_session}),
                ("text_delta", {"content": f"reply-{len(bodies)}"}),
                ("message_end", {}),
            ),
        )

    adapter = _adapter_with_transport(handler)
    first = ChatRequest(
        messages=[{"role": "user", "content": "第一轮"}],
        session_id="mme-same",
    )
    second = ChatRequest(
        messages=[
            {"role": "user", "content": "第一轮"},
            {"role": "assistant", "content": "reply-1"},
            {"role": "user", "content": "第二轮"},
        ],
        session_id="mme-same",
    )

    assert asyncio.run(adapter.chat(first)).reply == "reply-1"
    assert asyncio.run(adapter.chat(second)).reply == "reply-2"
    assert bodies == [
        {"content": "第一轮"},
        {"content": "第二轮", "sessionId": "cx-new"},
    ]
    asyncio.run(adapter.close())


def test_cx_agent_adapter_turns_sse_error_into_chat_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=_sse(
                ("session", {"sessionId": "cx-s1"}),
                ("error", {"message": "agent failed"}),
            ),
        )

    adapter = _adapter_with_transport(handler)
    resp = asyncio.run(
        adapter.chat(ChatRequest(messages=[{"role": "user", "content": "hi"}], session_id="mme-s1"))
    )

    assert resp.reply == ""
    assert resp.error == "agent failed"
    assert resp.raw["cx_session_id"] == "cx-s1"
    asyncio.run(adapter.close())


def test_cx_agent_adapter_rejects_preset_history_before_session():
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(500)

    adapter = _adapter_with_transport(handler)
    resp = asyncio.run(
        adapter.chat(
            ChatRequest(
                messages=[
                    {"role": "system", "content": "你是医生"},
                    {"role": "user", "content": "乳腺结节怎么办"},
                ],
                session_id="mme-s1",
            )
        )
    )

    assert called is False
    assert "preset history" in (resp.error or "")
    asyncio.run(adapter.close())


def test_cx_agent_adapter_requires_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CX_AGENT_TEST_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="CX_AGENT_TEST_TOKEN"):
        CxAgentAdapter(base_url="http://cx.local", test_token_env="CX_AGENT_TEST_TOKEN")
