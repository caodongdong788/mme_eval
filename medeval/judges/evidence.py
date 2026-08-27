"""LLM Judge 输出的原文证据核验工具。"""

from __future__ import annotations

import re
from typing import Any

from ..models import ConversationTrace


_FORMAT_MARKS = re.compile(r"[\s*_`>#|\-—–·•，。！？；：、,.!?;:'\"“”‘’（）()\[\]【】{}]+")


def _canonical(value: Any) -> str:
    """弱化排版差异，但不改写文字本身，供原文子串核验。"""

    return _FORMAT_MARKS.sub("", str(value or "")).casefold()


def assistant_texts(trace: ConversationTrace) -> list[str]:
    return [message.content for message in trace.messages if message.role == "assistant"]


def provided_context_texts(trace: ConversationTrace, initial_state: str) -> list[str]:
    """患者提供的对话事实与 Case 预置事实；不包含系统提示或 bot 回答。"""

    texts = [
        message.content
        for message in trace.messages
        if message.role == "user"
    ]
    if initial_state and initial_state != "无":
        texts.append(initial_state)
    return texts


def text_occurs(value: Any, sources: list[str]) -> bool:
    needle = _canonical(value)
    if len(needle) < 2:
        return False
    return any(needle in _canonical(source) for source in sources)


def sanitize_assistant_evidence(raw: Any, trace: ConversationTrace) -> tuple[list[str], list[str]]:
    """仅保留确实能在某条 bot 回复中找到的引文。"""

    if isinstance(raw, str):
        values = [raw]
    elif isinstance(raw, list):
        values = [str(value) for value in raw]
    else:
        values = []
    sources = assistant_texts(trace)
    valid: list[str] = []
    rejected: list[str] = []
    for value in values:
        quote = value.strip()
        if not quote:
            continue
        target = valid if text_occurs(quote, sources) else rejected
        if quote not in target:
            target.append(quote)
    return valid, rejected


def assistant_evidence_turn_refs(
    quotes: list[str], trace: ConversationTrace
) -> list[dict[str, str | int]]:
    """为已核验的 bot 引文保留可展示的对话轮次。

    Judge 的引文可能来自不同轮次；只返回裸字符串会让 Case 详情页把多条证据
    拼成一段，人工复核时无法知道应回看哪一轮。轮次口径与
    ``format_conversation`` 保持一致：每出现一条用户消息即进入下一轮。
    """

    refs: list[dict[str, str | int]] = []
    turn_index = 0
    for message in trace.messages:
        if message.role == "user":
            turn_index += 1
            continue
        if message.role != "assistant":
            continue
        for quote in quotes:
            if text_occurs(quote, [message.content]):
                ref = {"quote": quote, "turn_index": max(turn_index, 1)}
                if ref not in refs:
                    refs.append(ref)
    return refs


def normalize_terms(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    terms: list[str] = []
    for value in raw:
        term = str(value).strip()
        if len(_canonical(term)) >= 2 and term not in terms:
            terms.append(term)
    return terms


def term_hits(terms: list[str], sources: list[str]) -> list[str]:
    return [term for term in terms if text_occurs(term, sources)]
