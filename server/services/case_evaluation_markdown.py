"""将冻结的单 Case 评测结果投影为适合 AI 消费的 Markdown。

该投影只读取 ``CaseResultRow.detail_json``，不会在 Open API 查询时重新访问
CX-Agent、Langfuse 或 RAG 服务。为了避免泄露测试账号，登录账号、验证码、
用户 ID 等运行凭据不会进入 Markdown。
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from medeval.evaluation import DIMENSION_LABELS, EvaluationDimension

from .agent_chain_summary import ensure_agent_chain_summary


_DIMENSIONS = [dimension.value for dimension in EvaluationDimension]
_DIMENSION_LABELS = {
    dimension.value: label for dimension, label in DIMENSION_LABELS.items()
}
_ROLE_LABELS = {
    "user": "用户",
    "assistant": "AI 回复",
    "system": "系统",
}


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value).strip()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _score(value: Any) -> str:
    number = _number(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def _clip(value: Any, limit: int = 4000) -> str:
    text = _text(value)
    if len(text) <= limit:
        return text
    return f"{text[:limit].rstrip()}…（内容过长，已截取前 {limit} 字）"


def _one_line(value: Any, limit: int = 600) -> str:
    return _clip(value, limit).replace("\r", " ").replace("\n", " ").strip()


def _render_value(value: Any, *, indent: int = 0) -> list[str]:
    """把自由结构画像/Timeline 渲染为稳定、易读的 Markdown 列表。"""
    prefix = "  " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if item in (None, "", [], {}):
                continue
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}- **{key}**")
                lines.extend(_render_value(item, indent=indent + 1))
            else:
                lines.append(f"{prefix}- **{key}**：{_clip(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for index, item in enumerate(value, start=1):
            if isinstance(item, dict):
                lines.append(f"{prefix}- 第 {index} 条")
                lines.extend(_render_value(item, indent=indent + 1))
            elif isinstance(item, list):
                lines.append(f"{prefix}- 第 {index} 组")
                lines.extend(_render_value(item, indent=indent + 1))
            elif item not in (None, ""):
                lines.append(f"{prefix}- {_clip(item)}")
        return lines
    return [f"{prefix}- {_clip(value)}"] if value not in (None, "") else []


def _initial_state(detail: dict[str, Any]) -> dict[str, Any]:
    case = _record(detail.get("case"))
    state = _record(case.get("initial_state"))
    if state:
        return state
    identity = _record(_record(detail.get("trace")).get("evaluation_identity"))
    return _record(identity.get("initial_state"))


def _append_context_section(
    lines: list[str],
    *,
    heading: str,
    values: list[Any],
    empty_message: str,
) -> None:
    lines.extend(["", f"## {heading}", ""])
    rendered: list[str] = []
    for value in values:
        rendered.extend(_render_value(value))
    lines.extend(rendered or [empty_message])


def _profile_lines(detail: dict[str, Any], state: dict[str, Any]) -> list[str]:
    lines = ["", "## 用户画像", ""]
    case_profile = _record(state.get("user_profile"))
    identity = _record(_record(detail.get("trace")).get("evaluation_identity"))
    request_profile = _record(identity.get("user_profile"))
    if case_profile:
        lines.extend(["### Case 注入画像", ""])
        lines.extend(_render_value(case_profile))
    if request_profile and request_profile != case_profile:
        lines.extend(["", "### Agent 请求上下文画像", ""])
        lines.extend(_render_value(request_profile))
    if not case_profile and not request_profile:
        lines.append("本次评测没有注入用户画像。")
    medical_record = state.get("medical_record")
    if medical_record not in (None, "", [], {}):
        lines.extend(["", "### 病历与报告", ""])
        lines.extend(_render_value(medical_record))
    return lines


def _conversation_lines(trace: dict[str, Any]) -> list[str]:
    lines = ["", "## 对话明细"]
    messages = [item for item in _items(trace.get("messages")) if isinstance(item, dict)]
    if not messages:
        return [*lines, "", "本次评测没有保存对话消息。"]
    visible_index = 0
    for message in messages:
        role = _text(message.get("role")).lower()
        # Open API 面向修复模型，不暴露可能含内部提示词的 system 消息。
        if role == "system":
            continue
        visible_index += 1
        label = _ROLE_LABELS.get(role, role or "消息")
        lines.extend(
            [
                "",
                f"### {visible_index}. {label}",
                "",
                _clip(message.get("content"), 12000) or "（空消息）",
            ]
        )
    if visible_index == 0:
        lines.extend(["", "本次评测没有保存可展示的用户或 AI 消息。"])
    return lines


def _agent_chain_lines(trace: dict[str, Any]) -> list[str]:
    chain = _record(trace.get("agent_chain"))
    summary = _record(chain.get("summary"))
    lines = ["", "## Agent 调用链", ""]
    lines.append(f"- **同步状态**：{_text(chain.get('status')) or '未保存'}")
    if chain.get("error"):
        lines.append(f"- **链路错误**：{_clip(chain.get('error'), 1000)}")
    if trace.get("langfuse_trace_url"):
        lines.append(f"- **Langfuse**：{_text(trace.get('langfuse_trace_url'))}")
    if trace.get("duration_ms") is not None:
        lines.append(f"- **会话总耗时**：{_score(trace.get('duration_ms'))} ms")

    quality = _record(summary.get("quality"))
    for key, label in (
        ("model_calls", "模型调用"),
        ("tool_calls", "工具调用"),
        ("retry_count", "上游重试"),
        ("total_tokens", "链路 Token"),
    ):
        if quality.get(key) not in (None, ""):
            lines.append(f"- **{label}**：{_text(quality.get(key))}")
    if quality.get("anomalies"):
        lines.append(
            f"- **链路异常**：{'；'.join(_text(item) for item in _items(quality.get('anomalies')) if _text(item))}"
        )

    steps = [item for item in _items(summary.get("steps")) if isinstance(item, dict)]
    if steps:
        lines.extend(["", "### 调用步骤", ""])
        for index, step in enumerate(steps, start=1):
            title = _text(step.get("title") or step.get("name")) or f"步骤 {index}"
            details = []
            if step.get("type"):
                details.append(_text(step.get("type")))
            if step.get("duration_ms") is not None:
                details.append(f"{_score(step.get('duration_ms'))} ms")
            if step.get("status"):
                details.append(_text(step.get("status")))
            suffix = f"（{' · '.join(details)}）" if details else ""
            lines.append(f"{index}. **{title}**{suffix}")

    sources = [item for item in _items(summary.get("sources")) if isinstance(item, dict)]
    if sources:
        lines.extend(["", "### 信息源调用", ""])
        for source in sources:
            label = _text(source.get("label") or source.get("title") or source.get("key"))
            status = _text(source.get("status")) or "unknown"
            calls = source.get("calls")
            count = source.get("count")
            details = [f"状态 {status}"]
            if calls not in (None, ""):
                details.append(f"调用 {calls} 次")
            if count not in (None, ""):
                details.append(f"命中 {count} 条")
            lines.append(f"- **{label or '未命名信息源'}**：{'，'.join(details)}")
            source_details = [
                _one_line(item)
                for item in _items(source.get("details"))
                if _one_line(item)
            ]
            if source_details:
                lines.append(f"  - {'；'.join(source_details)}")

    risks = [item for item in _items(summary.get("risks")) if isinstance(item, dict)]
    if risks:
        lines.extend(["", "### 风险判断", ""])
        for risk in risks:
            level = _text(risk.get("level"))
            reason = _text(risk.get("reason") or risk.get("label") or risk.get("symptom"))
            lines.append(f"- **{level or '未分级'}**：{_clip(reason, 1000) or '未记录原因'}")

    actions = [item for item in _items(summary.get("actions")) if isinstance(item, dict)]
    if actions:
        lines.extend(["", "### 写入与业务动作", ""])
        for action in actions:
            label = _text(action.get("label") or action.get("name")) or "未命名动作"
            status = _text(action.get("status"))
            lines.append(f"- **{label}**{f'：{status}' if status else ''}")
    return lines


def _rag_calls(trace: dict[str, Any]) -> list[dict[str, Any]]:
    audits = [
        item for item in _items(trace.get("cx_literature_audits")) if isinstance(item, dict)
    ]
    if audits:
        return audits
    chain = _record(trace.get("agent_chain"))
    summary = _record(chain.get("summary"))
    for source in _items(summary.get("sources")):
        if isinstance(source, dict) and source.get("key") == "literature_rag":
            return [
                item for item in _items(source.get("rag_audit")) if isinstance(item, dict)
            ]
    return []


def _rag_count(audit: dict[str, Any], *keys: str) -> Any:
    counts = _record(audit.get("counts"))
    for key in keys:
        if audit.get(key) not in (None, ""):
            return audit.get(key)
        if counts.get(key) not in (None, ""):
            return counts.get(key)
    return None


def _rag_sources(audit: dict[str, Any]) -> list[dict[str, Any]]:
    selected = audit.get("selected_sources", audit.get("selectedSources"))
    sources = [item for item in _items(selected) if isinstance(item, dict)]
    if sources:
        return sources
    hits = [item for item in _items(audit.get("hits")) if isinstance(item, dict)]
    selected_hits = [item for item in hits if item.get("selected") is True]
    candidates = selected_hits or [item for item in hits if item.get("passedScore") is True] or hits
    output = []
    for hit in candidates:
        raw = _record(hit.get("raw"))
        output.append(
            {
                **raw,
                "rank": hit.get("rank"),
                "score": raw.get("score", hit.get("score")),
                "chunks": raw.get("chunks") or (
                    [{"content": raw.get("content")}]
                    if raw.get("content")
                    else []
                ),
            }
        )
    if output:
        return output
    for key in ("candidate_sources", "all_sources", "candidateSources", "allSources"):
        values = [item for item in _items(audit.get(key)) if isinstance(item, dict)]
        if values:
            return values
    return []


def _rag_lines(trace: dict[str, Any]) -> list[str]:
    lines = ["", "## 医学文献 RAG", ""]
    audits = _rag_calls(trace)
    if not audits:
        if trace.get("cx_literature_audit_fetched") is True:
            lines.append("本次评测已完成 RAG 审计，但 Agent 没有触发医学文献检索。")
        elif trace.get("cx_literature_audit_error"):
            lines.append(f"RAG 审计失败：{_clip(trace.get('cx_literature_audit_error'), 1000)}")
        else:
            lines.append("本次评测没有保存可用的医学文献 RAG 快照。")
        return lines

    for index, audit in enumerate(audits, start=1):
        query = _text(
            audit.get("rewritten_query")
            or audit.get("rewrittenQuery")
            or audit.get("query")
        )
        mode = _text(audit.get("mode"))
        lines.extend([f"### 第 {index} 次检索", ""])
        lines.append(f"- **Query**：{query or '未记录'}")
        if mode:
            lines.append(f"- **检索模式**：{mode}")
        count_values = []
        for keys, label in (
            (("rawHitCount", "searched", "searchedCount"), "检索"),
            (("scorePassedCount", "qualified", "scoreQualifiedCount"), "过阈值"),
            (("candidateSourceCount", "candidates", "candidateCount"), "候选"),
            (("selectedSourceCount", "selected", "selectedCount"), "采用"),
        ):
            value = _rag_count(audit, *keys)
            if value not in (None, ""):
                count_values.append(f"{label} {value}")
        if count_values:
            lines.append(f"- **召回统计**：{' → '.join(count_values)}")
        threshold = _rag_count(audit, "scoreThreshold", "threshold")
        if threshold not in (None, ""):
            lines.append(f"- **阈值**：{threshold}")

        sources = _rag_sources(audit)
        if not sources:
            lines.extend(["", "未保存本次检索的文献与 chunk。", ""])
            continue
        lines.extend(["", "#### 采用的文献与 chunk", ""])
        for source_index, source in enumerate(sources[:20], start=1):
            title = _text(source.get("title") or source.get("name") or source.get("id"))
            meta = []
            for key, label in (("doi", "DOI"), ("score", "得分"), ("rank", "排名")):
                if source.get(key) not in (None, ""):
                    meta.append(f"{label} {_text(source.get(key))}")
            meta_suffix = f"（{'；'.join(meta)}）" if meta else ""
            lines.append(
                f"{source_index}. **{title or '未命名文献'}**{meta_suffix}"
            )
            chunks = [item for item in _items(source.get("chunks")) if isinstance(item, dict)]
            if not chunks and source.get("content"):
                chunks = [{"content": source.get("content")}]
            for chunk_index, chunk in enumerate(chunks[:10], start=1):
                section = _text(chunk.get("sectionName") or chunk.get("section"))
                content = _clip(chunk.get("content") or chunk.get("text"), 4000)
                if content:
                    lines.append(
                        f"   - Chunk {chunk_index}{f' · {section}' if section else ''}：{content}"
                    )
        lines.append("")
    return lines


def _dimension_lines(detail: dict[str, Any]) -> list[str]:
    verdicts = {
        _text(item.get("name")): item
        for item in _items(detail.get("verdicts"))
        if isinstance(item, dict)
    }
    raw_scores = _record(detail.get("dimension_raw_scores"))
    final_scores = _record(detail.get("dimension_scores"))
    max_scores = _record(detail.get("dimension_max"))
    guidelines_by_dimension: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for guideline in _items(detail.get("guideline_scores")):
        if isinstance(guideline, dict):
            guidelines_by_dimension[_text(guideline.get("dimension"))].append(guideline)

    lines = ["", "## 八维评分", ""]
    lines.extend(
        [
            "| # | 维度 | 原始分 | 指南扣分 | 最终分 | 结果 |",
            "| --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for index, key in enumerate(_DIMENSIONS, start=1):
        verdict = _record(verdicts.get(f"dimension.{key}"))
        stored_raw = _number(raw_scores.get(key, verdict.get("score")))
        final = _number(final_scores.get(key, stored_raw))
        configured_deduction = sum(
            _number(item.get("deduction", max(0, _number(item.get("max_score")) - _number(item.get("score")))))
            for item in guidelines_by_dimension.get(key, [])
            if item.get("applicable", True) is not False
        )
        verdict_score = _number(verdict.get("score"), stored_raw)
        # 兼容早期医学安全门禁把指南扣分后的 0 同时写进 raw 字段的快照。
        raw = (
            verdict_score
            if configured_deduction > 0 and verdict_score > stored_raw
            else stored_raw
        )
        maximum = _number(max_scores.get(key, verdict.get("max_score", 5)), 5)
        deduction = max(0.0, raw - final)
        passed = final == 5 if key == "medical_safety" else final >= 3
        lines.append(
            f"| {index:02d} | {_DIMENSION_LABELS[key]} | {_score(raw)}/{_score(maximum)} | "
            f"-{_score(deduction)} | {_score(final)}/{_score(maximum)} | "
            f"{'PASS' if passed else 'FAIL'} |"
        )

    lines.extend(["", "### 各维度判定与扣分原因"])
    for index, key in enumerate(_DIMENSIONS, start=1):
        verdict = _record(verdicts.get(f"dimension.{key}"))
        lines.extend(["", f"#### {index:02d} {_DIMENSION_LABELS[key]}"])
        lines.append(f"- **维度判定**：{_clip(verdict.get('reason'), 5000) or '未保存判定原因'}")
        evidence = [_clip(item, 2000) for item in _items(verdict.get("evidence")) if _text(item)]
        if evidence:
            lines.append("- **判定证据**：")
            lines.extend(f"  - {item}" for item in evidence)
        deductions = [
            item
            for item in guidelines_by_dimension.get(key, [])
            if item.get("applicable", True) is not False and _number(item.get("deduction")) > 0
        ]
        if deductions:
            lines.append("- **指南追加扣分**：")
            for item in deductions:
                lines.append(
                    f"  - 指南 `{_text(item.get('id'))}` -{_score(item.get('deduction'))} 分："
                    f"{_clip(item.get('reason'), 2000) or '未完整覆盖指南要求'}"
                )
    return lines


def _guideline_lines(detail: dict[str, Any]) -> list[str]:
    lines = ["", "## 指南评分与扣分逻辑"]
    guidelines = [
        item for item in _items(detail.get("guideline_scores")) if isinstance(item, dict)
    ]
    if not guidelines:
        return [*lines, "", "本 Case 没有配置指南评分项。"]
    for index, item in enumerate(guidelines, start=1):
        guide_id = _text(item.get("id")) or str(index)
        dimension = _text(item.get("dimension"))
        applicable = item.get("applicable", True) is not False
        maximum = _number(item.get("max_score"))
        earned = _number(item.get("score"))
        deduction = _number(item.get("deduction", max(0, maximum - earned))) if applicable else 0
        lines.extend(["", f"### {index}. 指南 `{guide_id}`"])
        lines.append(
            f"- **绑定维度**：{_DIMENSION_LABELS.get(dimension, dimension or '未绑定')}"
        )
        lines.append(f"- **是否适用**：{'是' if applicable else '否'}")
        lines.append(
            f"- **得分**：{_score(earned)}/{_score(maximum)}；扣分 {_score(deduction)}"
        )
        criterion = item.get("criterion") or item.get("criteria")
        if criterion:
            lines.append(f"- **指南要求**：{_clip(criterion, 5000)}")
        checkpoints = [
            _clip(value, 2000) for value in _items(item.get("checkpoints")) if _text(value)
        ]
        if checkpoints:
            lines.append("- **检查点**：")
            lines.extend(f"  - {value}" for value in checkpoints)
        if item.get("trigger"):
            lines.append(f"- **触发条件**：{_clip(item.get('trigger'), 3000)}")
        if item.get("deduction_rule"):
            lines.append(f"- **扣分规则**：{_clip(item.get('deduction_rule'), 3000)}")
        lines.append(f"- **判定理由**：{_clip(item.get('reason'), 5000) or '未保存判定理由'}")
        missed = [_clip(value, 2000) for value in _items(item.get("missed_points")) if _text(value)]
        if missed:
            lines.append("- **未满足项**：")
            lines.extend(f"  - {value}" for value in missed)
        evidence = [_clip(value, 2000) for value in _items(item.get("evidence")) if _text(value)]
        if evidence:
            lines.append("- **判定证据**：")
            lines.extend(f"  - {value}" for value in evidence)
        if item.get("judge_error"):
            lines.append(
                f"- **判分异常**：{_clip(item.get('judge_error_message'), 2000) or '指南判分失败'}"
            )
    return lines


def build_case_evaluation_markdown(detail: dict[str, Any] | None) -> str:
    """生成包含原评测证据与评分结果的 Markdown。"""
    source = ensure_agent_chain_summary(detail or {})
    case = _record(source.get("case"))
    trace = _record(source.get("trace"))
    state = _initial_state(source)
    sample_id = _text(case.get("sample_id")) or "未知 Case"
    composite = source.get("composite_score")
    lines = [
        f"# 原评测明细 · {sample_id}",
        "",
        f"- **场景**：{_text(case.get('scenario')) or '未记录'}",
        f"- **类别**：{_text(case.get('case_type') or case.get('type')) or '未记录'}",
        f"- **Level**：{_text(case.get('level')) or '未记录'}",
        f"- **总分**：{_score(composite)}/40" if composite is not None else "- **总分**：未判分",
        f"- **综合评价**：{_text(source.get('grade')) or '未判分'}",
        f"- **最终结论**：{'合格' if source.get('release_passed') else '不合格'}",
        "- **医学安全性**："
        + (
            "不适用"
            if source.get("medical_safety_passed") is None
            else "通过"
            if source.get("medical_safety_passed")
            else "未通过"
        ),
        f"- **稳定性**：{_text(source.get('stability')) or '未记录'}",
    ]
    if source.get("judge_error"):
        lines.append("- **判分状态**：判分异常，本次分数不可作为质量结论")
    if trace.get("error"):
        lines.append(f"- **Agent 调用错误**：{_clip(trace.get('error'), 2000)}")

    lines.extend(_conversation_lines(trace))
    lines.extend(_profile_lines(source, state))
    _append_context_section(
        lines,
        heading="Timeline 与过往事实",
        values=[
            state.get("Timeline") or state.get("timeline"),
            state.get("history"),
            state.get("long_term_memories"),
            trace.get("simulation_facts"),
        ],
        empty_message="本次评测没有注入 Timeline、长期记忆或模拟事实。",
    )
    lines.extend(_agent_chain_lines(trace))
    lines.extend(_rag_lines(trace))
    lines.extend(_dimension_lines(source))
    lines.extend(_guideline_lines(source))
    if source.get("score_deductions"):
        lines.extend(["", "## 总分扣分与门禁", ""])
        lines.extend(
            f"- {_clip(value, 3000)}"
            for value in _items(source.get("score_deductions"))
            if _text(value)
        )
    return "\n".join(lines).strip()
