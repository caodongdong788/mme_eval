from __future__ import annotations

from medeval.models import ChatMessage, ConversationTrace
from medeval.visible_response import (
    normalize_cx_agent_visible_text,
    normalize_cx_agent_visible_trace,
)


def test_normalize_cx_visible_text_only_removes_heading_label() -> None:
    text = "### [护理] 什么时候抹\n正文引用[1]，链接[资料](https://example.com)"

    assert normalize_cx_agent_visible_text(text) == (
        "### 什么时候抹\n正文引用[1]，链接[资料](https://example.com)"
    )


def test_normalize_cx_visible_trace_preserves_raw_audit_payload() -> None:
    trace = ConversationTrace(
        messages=[ChatMessage(role="assistant", content="### [护理] 看哪些成分")],
        raw_responses=[{"events": [{"event": "text_delta", "data": {"content": "### [护理] 看哪些成分"}}]}],
    )

    normalized = normalize_cx_agent_visible_trace(trace)

    assert normalized.messages[0].content == "### 看哪些成分"
    assert normalized.raw_responses == trace.raw_responses
