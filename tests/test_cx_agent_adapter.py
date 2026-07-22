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
                ("evaluation_share", {"sharePath": "/s/11111111-1111-1111-1111-111111111111?cx_ui_release=current"}),
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
    assert resp.raw["cx_evaluation_share_url"] == (
        "http://cx.local/s/11111111-1111-1111-1111-111111111111?cx_ui_release=current"
    )
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


def test_cx_agent_adapter_replaces_inline_image_before_sending():
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode()))
        return httpx.Response(
            200,
            text=_sse(
                ("session", {"sessionId": "cx-image-1"}),
                ("text_delta", {"content": "已收到"}),
                ("message_end", {}),
            ),
        )

    adapter = _adapter_with_transport(handler)
    image = "data:image/jpeg;base64," + "a" * 260_100
    response = asyncio.run(
        adapter.chat(
            ChatRequest(
                messages=[{"role": "user", "content": f"[报告图] ({image})"}],
                session_id="mme-image-1",
            )
        )
    )

    assert response.reply == "已收到"
    assert "data:image" not in bodies[0]["content"]
    assert "图片附件已省略" in bodies[0]["content"]
    assert response.raw["input_sanitization"] == {
        "removed_inline_images": 1,
        "original_length": len(f"[报告图] ({image})"),
        "sent_length": len(bodies[0]["content"]),
        "truncated": False,
    }
    asyncio.run(adapter.close())


def test_cx_agent_adapter_sends_turn_images_in_dedicated_field():
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content.decode()))
        return httpx.Response(
            200,
            text=_sse(
                ("session", {"sessionId": "cx-image-2"}),
                ("text_delta", {"content": "已收到图片"}),
                ("message_end", {}),
            ),
        )

    adapter = _adapter_with_transport(handler)
    response = asyncio.run(
        adapter.chat(
            ChatRequest(
                messages=[{"role": "user", "content": "请解读这份报告"}],
                images=["data:image/jpeg;base64,aGVsbG8="],
                session_id="mme-image-2",
            )
        )
    )

    assert response.reply == "已收到图片"
    assert bodies == [{"content": "请解读这份报告", "images": ["data:image/jpeg;base64,aGVsbG8="]}]
    assert response.raw["input_images"] == {"count": 1}
    asyncio.run(adapter.close())


def test_cx_agent_adapter_uses_stateless_pool_without_initial_state():
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request.url.path)
        if request.url.path.endswith("/evaluation/accounts/lease"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "userId": "00000000-0000-0000-0000-000000000101",
                        "resetAt": "2026-07-21T08:00:00.000Z",
                        "profile": {},
                    },
                },
            )
        if request.url.path.endswith("/evaluation/accounts/release"):
            return httpx.Response(200, json={"success": True})
        return httpx.Response(
            200,
            text=_sse(
                ("session", {"sessionId": "cx-stateless-1"}),
                ("text_delta", {"content": "已收到"}),
                ("message_end", {}),
            ),
        )

    adapter = CxAgentAdapter(
        base_url="http://cx.local",
        test_token="token-1",
        isolated_accounts=True,
    )
    adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=10)

    response = asyncio.run(
        adapter.chat(
            ChatRequest(
                messages=[{"role": "user", "content": "普通问题"}],
                session_id="mme-stateless-1",
                metadata={"sample_id": "case-stateless"},
            )
        )
    )
    asyncio.run(adapter.end_session("mme-stateless-1"))

    assert response.reply == "已收到"
    assert response.raw["evaluation_account"]["test_user_id"].endswith("0101")
    assert requests == [
        "/api/test/evaluation/accounts/lease",
        "/api/test/chat/send",
        "/api/test/evaluation/accounts/release",
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


def test_cx_agent_adapter_leases_blank_account_and_exposes_trace_context(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv(
        "CX_AGENT_EVALUATION_LOGIN_CODES",
        "+8610000000201=418572",
    )
    requests: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        requests.append((request.url.path, body))
        if request.url.path.endswith("/evaluation/accounts/lease"):
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "userId": "00000000-0000-0000-0000-000000000201",
                        "resetAt": "2026-07-21T08:00:00.000Z",
                        "profile": {},
                    },
                },
            )
        if request.url.path.endswith("/evaluation/accounts/release"):
            return httpx.Response(200, json={"success": True})
        return httpx.Response(
            200,
            text=_sse(
                ("session", {"sessionId": "cx-isolated-1"}),
                (
                    "evaluation_context",
                    {
                        "traceId": "lf-trace-1",
                        "sessionId": "cx-isolated-1",
                        "testUserId": "00000000-0000-0000-0000-000000000201",
                        "userProfile": {},
                    },
                ),
                ("text_delta", {"content": "已收到"}),
                ("message_end", {}),
            ),
        )

    adapter = CxAgentAdapter(
        base_url="http://cx.local",
        test_token="token-1",
        isolated_accounts=True,
    )
    adapter._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), timeout=10)
    request = ChatRequest(
        messages=[{"role": "user", "content": "这是全新账户吗"}],
        session_id="mme-isolated-1",
        metadata={
            "eval_run_id": "run-1",
            "sample_id": "case-1",
            "run_idx": 0,
            "initial_state": {
                "user_profile": {"nickname": "小橙"},
                "long_term_memories": [
                    {
                        "key": "tamoxifen_schedule",
                        "category": "medication",
                        "label": "他莫昔芬服药时间",
                        "content": "晚上九点服用",
                        "memory_tier": "semantic",
                        "importance": 8,
                    }
                ],
            },
        },
    )

    response = asyncio.run(adapter.chat(request))
    asyncio.run(adapter.end_session("mme-isolated-1"))

    assert response.reply == "已收到"
    assert response.raw["cx_langfuse_trace_id"] == "lf-trace-1"
    assert response.raw["evaluation_account"] == {
        "login_account": "+8610000000201",
        "verification_code": "418572",
        "test_user_id": "00000000-0000-0000-0000-000000000201",
        "reset_at": "2026-07-21T08:00:00.000Z",
        "reset_status": "success",
        "profile_after_reset": {},
    }
    assert requests == [
        (
            "/api/test/evaluation/accounts/lease",
            {
                "leaseId": "mme-isolated-1",
                "initialState": {
                    "user_profile": {"nickname": "小橙"},
                    "long_term_memories": [
                        {
                            "key": "tamoxifen_schedule",
                            "category": "medication",
                            "label": "他莫昔芬服药时间",
                            "content": "晚上九点服用",
                            "memory_tier": "semantic",
                            "importance": 8,
                        }
                    ],
                },
            },
        ),
        (
            "/api/test/chat/send",
            {
                "content": "这是全新账户吗",
                "testUserId": "00000000-0000-0000-0000-000000000201",
                "evaluationLeaseId": "mme-isolated-1",
                "evalRunId": "run-1",
                "sampleId": "case-1",
                "runIdx": 0,
            },
        ),
        (
            "/api/test/evaluation/accounts/release",
            {
                "leaseId": "mme-isolated-1",
                "testUserId": "00000000-0000-0000-0000-000000000201",
            },
        ),
    ]
    asyncio.run(adapter.close())
