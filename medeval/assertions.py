"""基于运行证据的确定性断言。

这层刻意不检查“工具调用顺序是否长得完全一样”，只检查 Case 明确声明的
可验证结果：是否真正调用了一个高风险工具、是否有检索来源、状态是否写回、
对话是否包含必要文本，以及性能预算。医学内容正确性仍交给八维/指南 Judge。
"""

from __future__ import annotations

from typing import Any

from .models import CaseResult, ConversationTrace, EvaluationAssertion, FailureTag, JudgeVerdict, TestCase


def _lookup(value: Any, path: str) -> tuple[bool, Any]:
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return False, None
    return True, current


def _text_messages(trace: ConversationTrace) -> str:
    return "\n".join(
        str(message.get("content", "") if isinstance(message, dict) else getattr(message, "content", ""))
        for message in trace.messages
    )


def _chain_values(chain: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for key in keys:
        raw = chain.get(key, []) if isinstance(chain, dict) else []
        if isinstance(raw, list):
            values.extend(item for item in raw if isinstance(item, dict))
    return values


def _contains_name(items: list[dict[str, Any]], expected: str) -> int:
    needle = expected.strip().lower()
    if not needle:
        return 0
    matches = 0
    for item in items:
        fields = [item.get(key) for key in ("name", "tool", "key", "title", "label", "id", "category")]
        if any(needle == str(value).strip().lower() for value in fields if value is not None):
            matches += 1
    return matches


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
            items = _chain_values(chain, "actions", "steps", "nodes")
        else:
            items = _chain_values(chain, "sources", "steps", "nodes")
        count = _contains_name(items, assertion.name)
        passed = count >= assertion.min_count
        details.update({"expected": assertion.name, "count": count, "min_count": assertion.min_count})
        evidence = [str(item)[:240] for item in items if _contains_name([item], assertion.name)][:3]

    elif assertion.type == "transcript":
        transcript = _text_messages(trace)
        passed = assertion.contains.casefold() in transcript.casefold()
        details.update({"contains": assertion.contains, "message_count": len(trace.messages)})
        evidence = [assertion.contains] if passed else []

    elif assertion.type == "state":
        roots = {
            "initial_state": case.initial_state.model_dump(mode="json", by_alias=True),
            "evaluation_identity": trace.evaluation_identity,
            "simulation_facts": trace.simulation_facts,
            "agent_chain": trace.agent_chain,
        }
        exists, value = _lookup(roots, assertion.path)
        if not exists:
            # 只有链路路径不可用才属于 unavailable；其它路径不存在是可验证的 fail。
            if assertion.path.startswith("agent_chain.") and not trace.agent_chain:
                return _unavailable(assertion, "Agent 链路尚不可用，无法验证状态断言")
            passed = False
        elif assertion.equals is not None:
            passed = value == assertion.equals
        elif assertion.contains:
            passed = assertion.contains.casefold() in str(value).casefold()
        else:
            passed = bool(value)
        details.update({"path": assertion.path, "actual": value if exists else None, "exists": exists})
        evidence = [str(value)[:500]] if exists else []

    else:  # performance
        duration = float(trace.duration_ms or 0)
        tokens = sum(int(item.get("total_tokens", 0) or 0) for item in trace.turn_token_usage)
        chain = trace.agent_chain or {}
        actions = _chain_values(chain, "actions")
        checks: list[bool] = []
        if assertion.max_duration_ms is not None:
            checks.append(duration <= assertion.max_duration_ms)
        if assertion.max_total_tokens is not None:
            checks.append(tokens <= assertion.max_total_tokens)
        if assertion.max_tool_calls is not None:
            if not chain:
                return _unavailable(assertion, "未同步 Agent 链路，无法验证工具调用次数预算")
            checks.append(len(actions) <= assertion.max_tool_calls)
        passed = all(checks)
        details.update({"duration_ms": duration, "total_tokens": tokens, "tool_calls": len(actions)})
        evidence = [str(details)]

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
