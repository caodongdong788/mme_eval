"""Shared helpers for LLM-verified semantic transcript assertions."""

from __future__ import annotations

from ..models import ConversationTrace, FailureTag, JudgeVerdict, TestCase
from .evidence import assistant_texts, text_occurs


def format_semantic_assertions(case: TestCase) -> str:
    items = [item for item in case.evaluation.assertions if item.type == "transcript" and item.match_mode == "semantic"]
    if not items:
        return "无"
    return "\n".join(f"- id={item.id}；范围={item.scope}；要求={item.contains}" for item in items)


def semantic_assertion_verdicts(case: TestCase, trace: ConversationTrace, raw_results: object) -> list[JudgeVerdict]:
    results = raw_results if isinstance(raw_results, dict) else {}
    verdicts: list[JudgeVerdict] = []
    for assertion in case.evaluation.assertions:
        if assertion.type != "transcript" or assertion.match_mode != "semantic":
            continue
        raw = results.get(assertion.id, {})
        item = raw if isinstance(raw, dict) else {}
        requested_pass = item.get("passed") is True
        raw_evidence = item.get("evidence", [])
        values = [raw_evidence] if isinstance(raw_evidence, str) else raw_evidence if isinstance(raw_evidence, list) else []
        sources = assistant_texts(trace)
        if assertion.scope == "assistant_final":
            sources = sources[-1:] if sources else []
        evidence = [str(value).strip() for value in values if str(value).strip() and text_occurs(str(value).strip(), sources)]
        passed = requested_pass and bool(evidence)
        reason = str(item.get("reason") or "").strip()
        if requested_pass and not evidence:
            reason = "模型认为语义满足，但未提供可在指定 Agent 回答中定位的证据，按未满足处理"
        elif not reason:
            reason = "回答已语义满足该要求" if passed else f"回答未满足：{assertion.description}"
        verdicts.append(JudgeVerdict(
            name=f"assertion.{assertion.id}", passed=passed, score=1 if passed else 0, max_score=1,
            reason=reason, evidence=evidence,
            details={"status": "pass" if passed else "fail", "type": assertion.type, "match_mode": "semantic", "blocking": assertion.blocking, "scope": assertion.scope},
            failure_tags=[] if passed else [FailureTag.ASSERTION_FAILED.value],
        ))
    return verdicts
