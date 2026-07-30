"""把 cx-agent Langfuse observation 提炼成稳定、可展示的业务摘要。"""

from __future__ import annotations

from copy import deepcopy
import json
import re
from typing import Any, Iterable


_SOURCE_DEFINITIONS = (
    ("medical_records", "病例夹"),
    ("medical_metrics", "报告指标"),
    ("timeline", "健康 Timeline"),
    ("chat_history", "历史对话"),
    ("literature_rag", "医学文献 RAG"),
    ("current_report", "当前报告"),
)

_SOURCE_TOOL_KEYS = {
    "read_medical_metrics": "medical_metrics",
    "read_timeline": "timeline",
    "search_chat_history": "chat_history",
    "medical_literature_search": "literature_rag",
    "medical_report_consultation_board": "current_report",
}

_ACTION_LABELS = {
    "update_structured_profile": "更新用户画像",
    "schedule": "管理提醒任务",
    "generate_communication_card": "生成沟通卡",
    "generate_plan": "匹配辅助资源",
    "collect_info": "收集补充信息",
    "manage_check_in": "管理健康打卡",
    "analyze_meal_nutrition": "分析餐食营养",
    "read_cx_product_guide": "读取产品指南",
    "read_undercurrent_task": "读取暗流任务",
}

_CATEGORY_LABELS = {
    "current_symptom": "当前症状",
    "medication_treatment": "用药/治疗",
    "report_interpretation": "报告解读",
    "side_effect": "治疗副作用",
}

_PROTOCOL_PATTERNS = (
    re.compile(r"<\s*function_calls\b", re.I),
    re.compile(r"<\s*invoke\b", re.I),
    re.compile(r"<\s*functions\.", re.I),
)


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool):
        return None
    return value if isinstance(value, (int, float)) else None


def _tool_name(node: dict[str, Any]) -> str:
    return str(node.get("name") or "").removeprefix("tool.")


def _failed(node: dict[str, Any]) -> bool:
    metadata = _record(node.get("metadata"))
    return bool(
        str(node.get("level") or "").upper() == "ERROR"
        or node.get("status_message")
        or metadata.get("ok") is False
    )


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def _compact(value: Any, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", _text(value)).strip()
    return text if len(text) <= limit else f"{text[:limit].rstrip()}…"


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _regex_number(text: str, key: str) -> int | float | None:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*(-?\d+(?:\.\d+)?)', text)
    if not match:
        return None
    value = float(match.group(1))
    return int(value) if value.is_integer() else value


def _literature_payload(output: Any) -> tuple[dict[str, Any], str]:
    raw = _text(output)
    parsed = _json_object(output)
    return _record(parsed.get("literatureSearch")), raw


def _literature_titles(payload: dict[str, Any], raw: str) -> list[str]:
    titles: list[str] = []
    for key in ("selectedSources", "sources", "allSources"):
        for item in payload.get(key) or []:
            title = str(_record(item).get("title") or "").strip()
            if title and title not in titles:
                titles.append(title)
            if len(titles) == 3:
                return titles
    for match in re.finditer(r'"title"\s*:\s*"((?:\\.|[^"\\])*)"', raw):
        try:
            title = json.loads(f'"{match.group(1)}"').strip()
        except (json.JSONDecodeError, AttributeError):
            title = match.group(1).strip()
        if title and title not in titles:
            titles.append(title)
        if len(titles) == 3:
            break
    return titles


def _literature_sources(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    """保留 RAG 审计所需的文献与 chunk，供前端逐篇展开。

    不用摘要替代原始内容：评测需要审计「检索到什么、经过什么筛选、最终用了什么」。
    """
    values = payload.get(key)
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, dict)]


def _literature_audit(
    node: dict[str, Any], payload: dict[str, Any], raw: str
) -> dict[str, Any]:
    """构造单次 RAG 调用的可审计明细；截断时明确报告而不伪造文献。"""
    input_value = _record(node.get("input"))
    parsed = bool(payload)
    search = _record(payload)
    original_query = next(
        (
            str(input_value[key]).strip()
            for key in ("originalQuery", "original_query", "userQuery", "user_query")
            if input_value.get(key) not in (None, "")
        ),
        "",
    )
    rewritten_query = str(
        input_value.get("query") or search.get("query") or ""
    ).strip()
    return {
        "id": str(node.get("id") or ""),
        "status": "available" if parsed else "truncated",
        "unavailable_reason": (
            "Langfuse 保存的该工具输出已截断，无法可靠还原全部文献与 chunk"
            if not parsed and raw
            else "该工具未返回可解析的结构化检索结果"
            if not parsed
            else ""
        ),
        "original_query": original_query,
        "rewritten_query": rewritten_query,
        "mode": input_value.get("mode"),
        "counts": {
            "searched": _number(search.get("searchedCount")) or _regex_number(raw, "searchedCount"),
            "qualified": _number(search.get("scoreQualifiedCount")) or _regex_number(raw, "scoreQualifiedCount"),
            "candidates": _number(search.get("candidateCount")) or _regex_number(raw, "candidateCount"),
            "selected": _number(search.get("selectedCount")) or _regex_number(raw, "selectedCount"),
            "threshold": _number(search.get("scoreThreshold")) or _regex_number(raw, "scoreThreshold"),
        },
        # 上游有对应数组就原样保存；没有数组时只展示计数，绝不猜测具体哪些文献被筛掉。
        "all_sources": _literature_sources(search, "allSources"),
        "qualified_sources": _literature_sources(search, "qualifiedSources"),
        "candidate_sources": _literature_sources(search, "candidateSources"),
        "selected_sources": _literature_sources(search, "selectedSources"),
    }


def _source_items() -> list[dict[str, Any]]:
    return [
        {
            "key": key,
            "label": label,
            "status": "unused",
            "summary": "本轮未调用",
            "calls": 0,
            "count": 0,
            "details": [],
        }
        for key, label in _SOURCE_DEFINITIONS
    ]


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _summarize_source(
    source: dict[str, Any],
    node: dict[str, Any],
    tool: str,
) -> None:
    source["calls"] += 1
    input_value = _record(node.get("input"))
    output = node.get("output")
    output_text = _text(output)
    failed = _failed(node)
    if failed:
        source["status"] = "failed"
        source["summary"] = node.get("status_message") or "调用失败"
        return

    if tool == "saved_content":
        action = str(input_value.get("action") or "").lower()
        title = str(_record(output).get("title") or "").strip()
        attachment_count = int(
            _number(_record(node.get("metadata")).get("attachedDocumentCount")) or 0
        )
        if action == "read":
            source["status"] = "read"
            source["count"] += 1
            source["summary"] = f"读取 {source['count']} 份病例资料"
            if attachment_count:
                source["summary"] += f"（{attachment_count} 个附件）"
            _append_unique(source["details"], title or str(input_value.get("id") or "病例资料"))
        else:
            if source["status"] != "read":
                source["status"] = "listed"
                source["summary"] = "查看病例夹目录，未读取原始资料"
        return

    if tool == "read_medical_metrics":
        names = input_value.get("names") or []
        if isinstance(names, str):
            names = [names]
        source["query"] = [str(item) for item in names]
        missed = "暂时没有" in output_text or "没有找到" in output_text
        source["status"] = "miss" if missed else "hit"
        source["summary"] = "未命中结构化报告指标" if missed else "命中病历夹结构化指标"
        source["details"] = [_compact(output_text, 180)] if output_text else []
        return

    if tool == "read_timeline":
        source["status"] = "queried"
        source["summary"] = "读取健康 Timeline"
        source["query"] = {
            key: input_value[key]
            for key in ("keys", "query", "dateRange", "mode", "subject")
            if input_value.get(key) not in (None, "", [])
        }
        source["details"] = [_compact(output_text, 180)] if output_text else []
        return

    if tool == "search_chat_history":
        source["status"] = "hit" if output_text else "queried"
        source["summary"] = "检索历史对话" + ("并返回结果" if output_text else "")
        source["query"] = {
            key: input_value[key]
            for key in ("query", "dateRange", "sessionTitle", "limit")
            if input_value.get(key) not in (None, "", [])
        }
        return

    if tool == "medical_literature_search":
        payload, raw = _literature_payload(output)
        get_metric = lambda key: _number(payload.get(key)) or _regex_number(raw, key)  # noqa: E731
        metrics = {
            "searched": get_metric("searchedCount"),
            "qualified": get_metric("scoreQualifiedCount"),
            "candidates": get_metric("candidateCount"),
            "selected": get_metric("selectedCount"),
            "threshold": get_metric("scoreThreshold"),
        }
        selected = metrics["selected"]
        source["status"] = "hit" if selected is None or selected > 0 else "miss"
        source["summary"] = (
            f"检索 {metrics['searched']} 条，采用 {selected} 条"
            if metrics["searched"] is not None and selected is not None
            else "完成医学文献检索"
        )
        source["query"] = str(input_value.get("query") or payload.get("query") or "")
        source["mode"] = input_value.get("mode")
        source["metrics"] = metrics
        source["details"] = _literature_titles(payload, raw)
        source.setdefault("rag_audit", []).append(_literature_audit(node, payload, raw))
        return

    if tool == "medical_report_consultation_board":
        source["status"] = "read"
        source["summary"] = "读取并分析当前会话中的医学报告"
        source["details"] = [_compact(output_text, 180)] if output_text else []


def _action_summary(tool: str, node: dict[str, Any]) -> str:
    input_value = _record(node.get("input"))
    metadata = _record(node.get("metadata"))
    if tool == "update_structured_profile":
        auto_count = int(_number(metadata.get("autoUpdatedCount")) or 0)
        approval_count = int(_number(metadata.get("approvalCount")) or 0)
        return f"自动更新 {auto_count} 项，待确认 {approval_count} 项"
    if tool == "schedule":
        return f"{input_value.get('action') or '执行'} · {input_value.get('care_domain') or '通用提醒'}"
    if tool == "generate_communication_card":
        return f"卡片类型：{input_value.get('cardType') or '未记录'}"
    if tool == "generate_plan":
        return str(input_value.get("search_query") or input_value.get("type") or "匹配资源")
    if tool == "collect_info":
        return f"{input_value.get('mode') or '收集'} · {input_value.get('topic') or '补充信息'}"
    if tool == "manage_check_in":
        return str(input_value.get("mode") or "管理打卡")
    return _compact(input_value, 100) or "已调用"


def _usage(node: dict[str, Any], *keys: str) -> int | float:
    usage = _record(node.get("usage"))
    for key in keys:
        value = _number(usage.get(key))
        if value is not None:
            return value
    return 0


def _retry_attempts(metadata: dict[str, Any]) -> int:
    value = metadata.get("upstreamRetryAttempts")
    if isinstance(value, list):
        return len(value)
    return int(_number(value) or 0)


def _has_answer_content(node: dict[str, Any]) -> bool:
    output = node.get("output")
    if isinstance(output, dict):
        return bool(str(output.get("content") or "").strip())
    return bool(str(output or "").strip())


def _quality(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    models = [node for node in nodes if str(node.get("type") or "").upper() == "GENERATION"]
    tools = [node for node in nodes if str(node.get("type") or "").upper() == "TOOL"]
    input_tokens = sum(_usage(node, "input", "input_tokens", "prompt_tokens") for node in models)
    cached_tokens = sum(
        _usage(node, "cache_read_input_tokens", "cached_tokens", "cacheReadInputTokens")
        for node in models
    )
    output_tokens = sum(_usage(node, "output", "output_tokens", "completion_tokens") for node in models)
    total_tokens = sum(_usage(node, "total", "total_tokens", "totalTokens") for node in models)
    if not total_tokens:
        total_tokens = input_tokens + cached_tokens + output_tokens
    retry_count = sum(_retry_attempts(_record(node.get("metadata"))) for node in models)
    errors = [
        str(node.get("status_message") or f"{node.get('name') or '未知节点'} 调用失败")
        for node in nodes
        if _failed(node)
    ]
    anomalies: list[str] = []
    protocol_leaked = any(
        any(pattern.search(_text(node.get("output"))) for pattern in _PROTOCOL_PATTERNS)
        for node in nodes
        if str(node.get("type") or "").upper() in {"AGENT", "GENERATION"}
    )
    if protocol_leaked:
        anomalies.append("工具协议文本泄漏")
    if any(
        _record(node.get("metadata")).get("finalAnswerDetected") is False
        and _record(node.get("metadata")).get("stopReason") != "tool_calls"
        and not (_number(_record(node.get("metadata")).get("toolCallCount")) or 0)
        and not _has_answer_content(node)
        for node in models
    ):
        anomalies.append("模型未识别到最终回答")
    model_names = list(
        dict.fromkeys(str(node.get("model")) for node in models if node.get("model"))
    )
    provider_names = list(
        dict.fromkeys(
            str(_record(node.get("metadata")).get("provider"))
            for node in models
            if _record(node.get("metadata")).get("provider")
        )
    )
    root_durations = [
        _number(node.get("duration_ms"))
        for node in nodes
        if str(node.get("type") or "").upper() == "AGENT"
    ]
    total_duration = max((value for value in root_durations if value is not None), default=None)
    denominator = input_tokens + cached_tokens
    return {
        "total_duration_ms": total_duration,
        "model_calls": len(models),
        "tool_calls": len(tools),
        "tool_successes": sum(not _failed(node) for node in tools),
        "tool_failures": sum(_failed(node) for node in tools),
        "models": model_names,
        "providers": provider_names,
        "input_tokens": input_tokens,
        "cached_tokens": cached_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cache_hit_rate": round(cached_tokens / denominator, 4) if denominator else None,
        "retry_count": retry_count,
        "anomalies": anomalies,
        "errors": errors,
    }


def _steps(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_labels = dict(_SOURCE_DEFINITIONS)
    result: list[dict[str, Any]] = []
    model_index = 0
    for node in nodes:
        node_type = str(node.get("type") or "SPAN").upper()
        metadata = _record(node.get("metadata"))
        title = str(node.get("name") or "未命名节点")
        category = "span"
        summary = node_type
        if node_type == "AGENT":
            title = "Agent 接收请求"
            category = "agent"
            summary = "加载上下文并编排本轮任务"
        elif node_type == "GENERATION":
            model_index += 1
            title = str(node.get("model") or "未知模型")
            category = "model"
            tool_count = int(_number(metadata.get("toolCallCount")) or 0)
            summary = f"第 {metadata.get('loopCount') or model_index} 轮 · "
            summary += f"触发 {tool_count or 1} 个函数" if tool_count or metadata.get("stopReason") == "tool_calls" else "生成回答"
        elif node_type == "TOOL":
            tool = _tool_name(node)
            input_value = _record(node.get("input"))
            source_key = _SOURCE_TOOL_KEYS.get(tool)
            if tool == "saved_content" and str(input_value.get("type") or "").upper() == "C":
                source_key = "medical_records"
            if source_key:
                title = source_labels[source_key]
                category = "source"
                if tool == "medical_literature_search":
                    summary = str(input_value.get("query") or "医学文献检索")
                elif tool == "read_medical_metrics":
                    summary = f"指标：{_compact(input_value.get('names'), 70)}"
                elif tool == "saved_content":
                    summary = f"{input_value.get('action') or '读取'} · {input_value.get('id') or '病例夹'}"
                else:
                    summary = _compact(input_value, 90) or "读取信息"
            elif tool == "grade_medical_risk":
                title = "医学风险分级"
                category = "risk"
                summary = f"{input_value.get('level') or '—'} · {_compact(input_value.get('symptom'), 65)}"
            elif tool in _ACTION_LABELS:
                title = _ACTION_LABELS[tool]
                category = "action"
                summary = _action_summary(tool, node)
            else:
                title = tool or title
                category = "tool"
                summary = _compact(node.get("input"), 90) or "无参数"
        result.append(
            {
                "id": str(node.get("id") or len(result)),
                "title": title,
                "category": category,
                "summary": summary,
                "duration_ms": _number(node.get("duration_ms")),
                "status": "failed" if _failed(node) else "success",
            }
        )
    return result


def summarize_agent_chain(nodes: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """按 cx-agent 的稳定工具协议生成无模型依赖的链路摘要。"""
    node_list = [node for node in nodes if isinstance(node, dict)]
    sources = _source_items()
    source_by_key = {item["key"]: item for item in sources}
    risks: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []

    for node in node_list:
        if str(node.get("type") or "").upper() != "TOOL":
            continue
        tool = _tool_name(node)
        input_value = _record(node.get("input"))
        source_key = _SOURCE_TOOL_KEYS.get(tool)
        if tool == "saved_content" and str(input_value.get("type") or "").upper() == "C":
            source_key = "medical_records"
        if source_key:
            _summarize_source(source_by_key[source_key], node, tool)
            continue
        if tool == "grade_medical_risk":
            risks.append(
                {
                    "level": str(input_value.get("level") or "—"),
                    "category": _CATEGORY_LABELS.get(
                        str(input_value.get("category") or ""),
                        str(input_value.get("category") or "—"),
                    ),
                    "symptom": _compact(input_value.get("symptom")),
                    "reason": _compact(input_value.get("reason"), 200),
                    "status": "failed" if _failed(node) else "success",
                }
            )
            continue
        if tool in _ACTION_LABELS:
            actions.append(
                {
                    "tool": tool,
                    "label": _ACTION_LABELS[tool],
                    "summary": _action_summary(tool, node),
                    "status": "failed" if _failed(node) else "success",
                }
            )
        elif tool == "saved_content":
            actions.append(
                {
                    "tool": tool,
                    "label": "读取历史内容",
                    "summary": f"类型 {input_value.get('type') or '—'} · {input_value.get('action') or '—'}",
                    "status": "failed" if _failed(node) else "success",
                }
            )

    return {
        "schema_version": "1.0",
        "steps": _steps(node_list),
        "sources": sources,
        "risks": risks,
        "actions": actions,
        "quality": _quality(node_list),
    }


def _snapshot_chunk(hit: dict[str, Any]) -> dict[str, Any] | None:
    raw = _record(hit.get("raw"))
    content = str(raw.get("content") or "").strip()
    if not content:
        return None
    return {
        "sourceRank": _number(hit.get("rank")),
        "score": _number(raw.get("score")) or _number(raw.get("vec_score")),
        "title": str(raw.get("title") or "未命名文献"),
        "content": content,
        "sectionName": raw.get("section_name"),
        "chunkType": raw.get("chunk_type"),
        "raw": raw,
    }


def _snapshot_sources(hits: list[dict[str, Any]], flag: str | None = None) -> list[dict[str, Any]]:
    """把 cx-agent 审计表的原始 hit 按文献聚合为前端可展开的数据。

    ``flag`` 只使用审计表明确记录的门控结果；候选阶段没有逐条标记时绝不反推。
    """
    grouped: dict[str, dict[str, Any]] = {}
    for hit in hits:
        if flag is not None and hit.get(flag) is not True:
            continue
        raw = _record(hit.get("raw"))
        chunk = _snapshot_chunk(hit)
        if chunk is None:
            continue
        title = str(raw.get("title") or "未命名文献")
        doi = str(raw.get("doi") or "").strip()
        key = doi.lower() or "|".join(
            [title.lower(), str(raw.get("pub_year") or ""), str(raw.get("journal") or "")]
        )
        source = grouped.setdefault(
            key,
            {
                "id": doi or key,
                "title": title,
                "doi": doi or None,
                "journal": raw.get("journal"),
                "pubYear": raw.get("pub_year"),
                "score": chunk.get("score"),
                "articleClass": raw.get("article_class"),
                "sourceTier": raw.get("source_tier"),
                "confidenceLevel": raw.get("confidence_level"),
                "chunks": [],
            },
        )
        source["chunks"].append(chunk)
        score = _number(chunk.get("score"))
        if score is not None and (source.get("score") is None or score > source["score"]):
            source["score"] = score
    return list(grouped.values())


def _snapshot_rag_calls(audits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for audit in audits:
        hits = [item for item in audit.get("hits") or [] if isinstance(item, dict)]
        calls.append(
            {
                "id": str(audit.get("id") or audit.get("toolCallId") or ""),
                "status": "available",
                "original_query": "",
                "rewritten_query": str(audit.get("query") or ""),
                "mode": audit.get("mode"),
                "counts": {
                    "searched": _number(audit.get("rawHitCount")),
                    "qualified": _number(audit.get("scorePassedCount")),
                    "candidates": _number(audit.get("candidateSourceCount")),
                    "selected": _number(audit.get("selectedSourceCount")),
                    "threshold": _number(audit.get("scoreThreshold")),
                },
                "all_sources": _snapshot_sources(hits),
                "qualified_sources": _snapshot_sources(hits, "passedScore"),
                # 审计表未为每条 hit 记录 reranker 的 candidate 标记；只展示总数，避免误导。
                "candidate_sources": [],
                "selected_sources": _snapshot_sources(hits, "selected"),
                "snapshot_source": "cx_agent_audit_db",
            }
        )
    return calls


def apply_literature_audit_snapshot(
    agent_chain: dict[str, Any], audits: list[dict[str, Any]]
) -> dict[str, Any]:
    """把 cx-agent 审计快照叠加到 Langfuse 链路摘要中。

    快照优先于 Langfuse 的截断工具输出；其余调用链仍保持 Langfuse 数据不变。
    """
    if not audits:
        return agent_chain
    chain = deepcopy(agent_chain)
    nodes = chain.get("nodes") if isinstance(chain.get("nodes"), list) else []
    summary = _record(chain.get("summary")) or summarize_agent_chain(nodes)
    sources = summary.get("sources") if isinstance(summary.get("sources"), list) else _source_items()
    rag = next(
        (item for item in sources if isinstance(item, dict) and item.get("key") == "literature_rag"),
        None,
    )
    if rag is None:
        rag = {"key": "literature_rag", "label": "医学文献 RAG"}
        sources.append(rag)
    calls = _snapshot_rag_calls(audits)
    selected = sum(int(call["counts"].get("selected") or 0) for call in calls)
    rag.update(
        {
            "status": "hit" if selected else "miss",
            "summary": f"已固化 {len(calls)} 次检索的完整召回 chunk",
            "calls": len(calls),
            "count": selected,
            "details": [],
            "metrics": calls[-1]["counts"],
            "rag_audit": calls,
        }
    )
    summary["sources"] = sources
    chain["summary"] = summary
    return chain


def ensure_agent_chain_summary(detail: dict[str, Any]) -> dict[str, Any]:
    """为历史保存的 detail_json 即时补摘要，不回写、不修改传入对象。"""
    hydrated = deepcopy(detail)
    trace = _record(hydrated.get("trace"))
    chain = _record(trace.get("agent_chain"))
    nodes = chain.get("nodes")
    if isinstance(nodes, list):
        chain["summary"] = summarize_agent_chain(nodes)
    audits = [item for item in trace.get("cx_literature_audits") or [] if isinstance(item, dict)]
    chain = apply_literature_audit_snapshot(chain, audits)
    if chain:
        trace["agent_chain"] = chain
        hydrated["trace"] = trace
    return hydrated
