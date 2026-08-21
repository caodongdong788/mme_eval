"""Judge 共用的对话文本渲染。"""

from __future__ import annotations

import re
from typing import Any

from ..models import ConversationTrace


_MAX_RAG_AUDITS = 3
_MAX_RAG_SOURCES_PER_AUDIT = 8
_MAX_RAG_SOURCE_CHARS = 900
_MAX_RAG_CONTEXT_CHARS = 12_000


def _rag_text(value: object, *, limit: int = _MAX_RAG_SOURCE_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}…"


def _rag_source_payload(source: dict[str, Any]) -> dict[str, Any]:
    raw = source.get("raw")
    return raw if isinstance(raw, dict) else source


def _selected_rag_sources(audit: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("selected_sources", "selectedSources"):
        values = audit.get(key)
        if isinstance(values, list):
            selected = [item for item in values if isinstance(item, dict)]
            if selected:
                return selected
    hits = audit.get("hits")
    if not isinstance(hits, list):
        return []
    return [
        item for item in hits
        if isinstance(item, dict) and item.get("selected") is True
    ]


def _rag_source_excerpt(source: dict[str, Any]) -> str:
    payload = _rag_source_payload(source)
    direct = payload.get("translation") or payload.get("content")
    if direct:
        return _rag_text(direct)
    chunks = payload.get("chunks")
    if not isinstance(chunks, list):
        return ""
    return _rag_text(" ".join(
        str(chunk.get("translation") or chunk.get("content") or "")
        for chunk in chunks
        if isinstance(chunk, dict)
    ))


def format_conversation(trace: ConversationTrace) -> str:
    lines: list[str] = []
    turn_index = 0
    evidence_index = 0
    for message in trace.messages:
        if message.role == "system":
            lines.append(f"[系统提示] {message.content}")
        elif message.role == "user":
            turn_index += 1
            lines.append(f"[turn {turn_index} · 用户] {message.content}")
        else:
            evidence_index += 1
            lines.append(
                f"[turn {max(turn_index, 1)} · bot · 证据 B{evidence_index}] "
                f"{message.content}"
            )
    return "\n".join(lines)


def format_rag_evidence(trace: ConversationTrace) -> str:
    """渲染本次回答实际采用的冻结 RAG 证据，供 Judge 核对医学事实。

    只纳入 ``selected`` 文献，不把原始召回或未采用候选混成回答依据；同时限制
    数量与长度，避免完整审计快照挤占 Judge 上下文。
    """

    audits = [
        item for item in trace.cx_literature_audits
        if isinstance(item, dict)
    ]
    if not audits:
        return "本次回答没有可用的最终采用 RAG 文献证据。"

    lines: list[str] = []
    truncated = len(audits) > _MAX_RAG_AUDITS
    for audit_index, audit in enumerate(audits[:_MAX_RAG_AUDITS], start=1):
        query = _rag_text(
            audit.get("rewritten_query")
            or audit.get("rewrittenQuery")
            or audit.get("query"),
            limit=300,
        )
        lines.append(f"[检索 {audit_index}] Query：{query or '未记录'}")
        sources = _selected_rag_sources(audit)
        if not sources:
            lines.append("- 没有冻结的最终采用文献。")
            continue
        if len(sources) > _MAX_RAG_SOURCES_PER_AUDIT:
            truncated = True
        for source_index, source in enumerate(
            sources[:_MAX_RAG_SOURCES_PER_AUDIT], start=1
        ):
            payload = _rag_source_payload(source)
            source_id = (
                source.get("rank")
                or payload.get("rank")
                or source_index
            )
            title = _rag_text(
                payload.get("title_translation") or payload.get("title") or "未命名文献",
                limit=300,
            )
            excerpt = _rag_source_excerpt(source)
            lines.append(f"- [来源 {source_id}] {title}：{excerpt or '未保存正文片段'}")
            if sum(len(line) for line in lines) >= _MAX_RAG_CONTEXT_CHARS:
                truncated = True
                break
        if sum(len(line) for line in lines) >= _MAX_RAG_CONTEXT_CHARS:
            break
    if truncated:
        lines.append("- 其余 RAG 证据因判分上下文长度限制未展示。")
    return "\n".join(lines)
