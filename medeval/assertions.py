"""基于运行证据的确定性断言。

这层刻意不检查“工具调用顺序是否长得完全一样”，只检查 Case 明确声明的
可验证结果：是否真正调用了一个高风险工具、是否有检索来源、对话是否包含
必要文本。医学内容正确性仍交给八维/指南 Judge。
"""

from __future__ import annotations

from typing import Any

from .models import CaseResult, ConversationTrace, EvaluationAssertion, FailureTag, JudgeVerdict, TestCase


def _text_messages(trace: ConversationTrace) -> str:
    return "\n".join(
        str(message.get("content", "") if isinstance(message, dict) else getattr(message, "content", ""))
        for message in trace.messages
    )


def _message_role(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("role", "")).strip().lower()
    return str(getattr(message, "role", "")).strip().lower()


def _message_content(message: Any) -> str:
    return str(message.get("content", "") if isinstance(message, dict) else getattr(message, "content", ""))


def _transcript_scope(trace: ConversationTrace, scope: str) -> tuple[str, int]:
    """返回断言真正检查的内容和消息数。

    ``full_conversation`` 专门保留给历史 YAML；新用例应选 ``assistant_final``，
    防止用户自己的提问文本让“回答要求”被误判为满足。
    """
    if scope == "assistant_final":
        for message in reversed(trace.messages):
            if _message_role(message) == "assistant":
                return _message_content(message), 1
        return "", 0
    if scope == "assistant_messages":
        messages = [message for message in trace.messages if _message_role(message) == "assistant"]
        return "\n".join(_message_content(message) for message in messages), len(messages)
    return _text_messages(trace), len(trace.messages)


def _chain_values(chain: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for key in keys:
        raw = chain.get(key, []) if isinstance(chain, dict) else []
        if isinstance(raw, list):
            values.extend(item for item in raw if isinstance(item, dict))
    return values


def _contains_name(items: list[dict[str, Any]], expected: str) -> int:
    def normalized(value: Any) -> str:
        name = str(value or "").strip().lower()
        # OpenTelemetry/Langfuse 的工具 observation 使用 ``tool.<工具名>``，
        # Case YAML 只保存业务工具名。两者语义相同，断言匹配前统一去掉链路前缀。
        return name.removeprefix("tool.")

    needle = normalized(expected)
    if not needle:
        return 0
    matches = 0
    for item in items:
        fields = [item.get(key) for key in ("name", "tool", "key", "title", "label", "id", "category")]
        if any(needle == normalized(value) for value in fields if value is not None):
            matches += 1
    return matches


def _tool_call_result(
    chain: dict[str, Any], expected: str
) -> tuple[int, list[dict[str, Any]]]:
    """读取工具调用次数，并兼容独立留档的医学文献 RAG 审计证据。

    大多数工具直接记录在 Agent 调用节点中；医学文献检索还会单独写入审计表，
    审计快照可能比 Langfuse 工具节点更完整。此时 ``literature_rag.calls`` 能确定
    ``medical_literature_search`` 实际执行过，但不能代表一定检索命中；是否命中仍由
    retrieval 断言单独判断。
    """
    items = _chain_values(chain, "actions", "steps", "nodes")
    matched = [item for item in items if _contains_name([item], expected)]
    count = len(matched)
    if count or expected.strip().lower() != "medical_literature_search":
        return count, matched

    summary = chain.get("summary") if isinstance(chain, dict) else None
    sources = _chain_values(summary if isinstance(summary, dict) else {}, "sources")
    literature_sources = [
        item for item in sources if _contains_name([item], "literature_rag")
    ]
    audit_calls = 0
    for item in literature_sources:
        raw_calls = item.get("calls")
        if isinstance(raw_calls, (int, float)) and not isinstance(raw_calls, bool):
            audit_calls += max(0, int(raw_calls))
    return audit_calls, literature_sources if audit_calls else []


def _retrieval_source_result(
    chain: dict[str, Any], expected: str
) -> tuple[int, list[dict[str, Any]]]:
    """读取业务来源摘要，返回已确认的有效数据命中数。

    工具节点只能证明“调用过”；真正的数据命中状态位于
    ``agent_chain.summary.sources``。旧快照没有摘要时仍回退原有节点匹配，保证历史
    YAML 可读，但新链路优先采用 hit/read 与 count 的确定性结果。
    """
    expected = {"medical_literature": "literature_rag"}.get(expected, expected)
    summary = chain.get("summary") if isinstance(chain, dict) else None
    summary_sources = _chain_values(summary if isinstance(summary, dict) else {}, "sources")
    matched = [item for item in summary_sources if _contains_name([item], expected)]
    if matched:
        count = 0
        for item in matched:
            status = str(item.get("status") or "").strip().lower()
            if status not in {"hit", "read"}:
                continue
            raw_count = item.get("count")
            if isinstance(raw_count, (int, float)) and not isinstance(raw_count, bool):
                count += max(0, int(raw_count))
            if not raw_count:
                raw_calls = item.get("calls")
                count += (
                    max(1, int(raw_calls))
                    if isinstance(raw_calls, (int, float)) and not isinstance(raw_calls, bool)
                    else 1
                )
        return count, matched

    # 兼容旧快照：当时来源/步骤可能直接放在 agent_chain 顶层。
    legacy_items = _chain_values(chain, "sources", "steps", "nodes")
    return _contains_name(legacy_items, expected), [
        item for item in legacy_items if _contains_name([item], expected)
    ]


def _unavailable(assertion: EvaluationAssertion, reason: str) -> JudgeVerdict:
    failed = assertion.on_unavailable == "fail"
    return JudgeVerdict(
        name=f"assertion.{assertion.id}",
        passed=not failed,
        score=0,
        max_score=1,
        reason=reason,
        details={"status": "unavailable", "blocking": assertion.blocking and failed, "type": assertion.type},
        failure_tags=[FailureTag.ASSERTION_FAILED.value] if failed else [],
    )


def evaluate_assertion(case: TestCase, trace: ConversationTrace, assertion: EvaluationAssertion) -> JudgeVerdict:
    """返回单条断言 verdict；未接通可观测性时按 Case 策略标记 unavailable。"""
    passed = False
    evidence: list[str] = []
    details: dict[str, Any] = {"type": assertion.type, "blocking": assertion.blocking}

    if assertion.type in {"tool_call", "retrieval"}:
        chain = trace.agent_chain or {}
        if not chain:
            return _unavailable(assertion, "未同步到 Langfuse/Agent 链路，无法验证该断言")
        if assertion.type == "tool_call":
            count, matched_calls = _tool_call_result(chain, assertion.name)
            evidence = [str(item)[:500] for item in matched_calls][:3]
        else:
            count, matched_sources = _retrieval_source_result(chain, assertion.name)
            evidence = [str(item)[:500] for item in matched_sources][:3]
        passed = count >= assertion.min_count
        details.update({"expected": assertion.name, "count": count, "min_count": assertion.min_count})

    elif assertion.type == "transcript":
        transcript, checked_message_count = _transcript_scope(trace, assertion.scope)
        passed = assertion.contains.casefold() in transcript.casefold()
        details.update({
            "contains": assertion.contains,
            "scope": assertion.scope,
            "message_count": len(trace.messages),
            "checked_message_count": checked_message_count,
        })
        evidence = [assertion.contains] if passed else []

    return JudgeVerdict(
        name=f"assertion.{assertion.id}",
        passed=passed,
        score=1 if passed else 0,
        max_score=1,
        reason=("断言满足" if passed else f"断言未满足：{assertion.description}"),
        evidence=evidence,
        details={**details, "status": "pass" if passed else "fail"},
        failure_tags=[FailureTag.ASSERTION_FAILED.value] if not passed else [],
    )


def evaluate_assertions(case: TestCase, trace: ConversationTrace) -> list[JudgeVerdict]:
    return [evaluate_assertion(case, trace, item) for item in case.evaluation.assertions]


def refresh_result_assertions(result: CaseResult) -> None:
    """在 Langfuse 同步后替换断言 verdict，使工具/RAG 证据为真实最终结果。"""
    retained = [verdict for verdict in result.verdicts if not verdict.name.startswith("assertion.")]
    result.verdicts = [*retained, *evaluate_assertions(result.case, result.trace)]
