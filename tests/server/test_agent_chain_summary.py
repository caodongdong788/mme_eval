from __future__ import annotations

from server.services.agent_chain_summary import (
    apply_literature_audit_snapshot,
    ensure_agent_chain_summary,
    summarize_agent_chain,
)


def _tool(
    node_id: str,
    name: str,
    *,
    input: object | None = None,
    output: object | None = None,
    metadata: dict | None = None,
) -> dict:
    return {
        "id": node_id,
        "type": "TOOL",
        "name": name,
        "input": input,
        "output": output,
        "metadata": metadata or {"ok": True},
        "duration_ms": 120,
    }


def test_summarizes_medical_sources_without_treating_history_as_rag():
    summary = summarize_agent_chain(
        [
            _tool(
                "folder",
                "tool.saved_content",
                input={"action": "read", "type": "C", "id": "report-1"},
                output={"action": "read", "type": "C", "title": "术后病理", "imageCount": 2},
                metadata={"ok": True, "attachedDocumentCount": 2},
            ),
            _tool(
                "metrics",
                "tool.read_medical_metrics",
                input={"names": ["ER", "PR"]},
                output="## 报告指标结果（来自病历夹结构化索引）\nER 阳性；PR 阳性",
            ),
            _tool(
                "history",
                "tool.search_chat_history",
                input={"query": "上次复查", "limit": 5},
                output="找到 2 轮历史对话",
            ),
        ]
    )

    sources = {item["key"]: item for item in summary["sources"]}
    assert sources["medical_records"]["status"] == "read"
    assert sources["medical_records"]["count"] == 1
    assert "术后病理" in sources["medical_records"]["details"]
    assert sources["medical_metrics"]["status"] == "hit"
    assert sources["chat_history"]["status"] == "hit"
    assert sources["literature_rag"]["status"] == "unused"


def test_summarizes_literature_recall_risk_actions_and_chain_quality():
    summary = summarize_agent_chain(
        [
            {
                "id": "agent",
                "type": "AGENT",
                "name": "cx.agent.chat.test",
                "duration_ms": 18327,
                "output": "<function_calls><invoke name=\"schedule\"></invoke></function_calls>",
            },
            {
                "id": "llm",
                "type": "GENERATION",
                "name": "llm.chat.completions",
                "model": "kimi-k2.5",
                "duration_ms": 8589,
                "usage": {
                    "input": 1000,
                    "cache_read_input_tokens": 3000,
                    "output": 500,
                    "total": 4500,
                },
                "metadata": {
                    "provider": "dashscope",
                    "upstreamRetryAttempts": 2,
                    "finalAnswerDetected": False,
                },
            },
            _tool(
                "rag",
                "tool.medical_literature_search",
                input={"query": "他莫昔芬漏服", "mode": "drug"},
                output=(
                    '{"literatureSearch":{"searchedCount":25,"scoreThreshold":0.65,'
                    '"scoreQualifiedCount":17,"candidateCount":17,"selectedCount":2,'
                    '"allSources":[{"id":"drug-label","title":"药品说明书",'
                    '"chunks":[{"content":"每日一次","sectionName":"用法"}]}],'
                    '"selectedSources":[{"id":"drug-label","title":"药品说明书"}]}}'
                ),
            ),
            _tool(
                "risk",
                "tool.grade_medical_risk",
                input={
                    "level": "B0",
                    "category": "current_symptom",
                    "symptom": "术侧上肢肿胀",
                    "reason": "需排除血栓",
                },
            ),
            _tool(
                "profile",
                "tool.update_structured_profile",
                input={"updates": {"nickname": "小橙"}},
                metadata={"ok": True, "autoUpdatedCount": 1, "approvalCount": 0},
            ),
        ]
    )

    rag = next(item for item in summary["sources"] if item["key"] == "literature_rag")
    assert rag["status"] == "hit"
    assert rag["metrics"] == {
        "searched": 25,
        "qualified": 17,
        "candidates": 17,
        "selected": 2,
        "threshold": 0.65,
    }
    assert rag["details"] == ["药品说明书"]
    assert rag["rag_audit"][0]["status"] == "available"
    assert rag["rag_audit"][0]["rewritten_query"] == "他莫昔芬漏服"
    assert rag["rag_audit"][0]["all_sources"][0]["chunks"][0]["content"] == "每日一次"
    assert summary["risks"][0]["level"] == "B0"
    assert summary["actions"][0]["label"] == "更新用户画像"
    assert [step["title"] for step in summary["steps"]] == [
        "Agent 接收请求",
        "kimi-k2.5",
        "医学文献 RAG",
        "医学风险分级",
        "更新用户画像",
    ]
    assert summary["quality"]["retry_count"] == 2
    assert summary["quality"]["total_tokens"] == 4500
    assert summary["quality"]["cache_hit_rate"] == 0.75
    assert "工具协议文本泄漏" in summary["quality"]["anomalies"]
    assert "模型未识别到最终回答" in summary["quality"]["anomalies"]


def test_ensure_agent_chain_summary_hydrates_old_detail_without_mutating_input():
    detail = {
        "trace": {
            "agent_chain": {
                "status": "synced",
                "nodes": [
                    _tool(
                        "timeline",
                        "tool.read_timeline",
                        input={"keys": ["复查"]},
                        output="2026-08-20：复查白细胞 3.2×10^9/L",
                    )
                ],
            }
        }
    }

    hydrated = ensure_agent_chain_summary(detail)

    assert "summary" not in detail["trace"]["agent_chain"]
    timeline = hydrated["trace"]["agent_chain"]["summary"]["sources"][2]
    assert timeline["status"] == "hit"
    assert timeline["count"] == 1


def test_summarizes_empty_source_results_as_misses():
    summary = summarize_agent_chain(
        [
            _tool(
                "metrics",
                "tool.read_medical_metrics",
                input={"names": ["CA15-3"]},
                output="结构化指标索引里暂时没有找到 CA15-3。",
            ),
            _tool(
                "timeline",
                "tool.read_timeline",
                input={"keys": ["wbc"]},
                output="（这些 key 下暂无记录）",
            ),
            _tool(
                "history",
                "tool.search_chat_history",
                input={"query": "复查"},
                output="没有找到匹配的历史对话。",
            ),
        ]
    )

    sources = {item["key"]: item for item in summary["sources"]}
    assert sources["medical_metrics"]["status"] == "miss"
    assert sources["timeline"]["status"] == "miss"
    assert sources["chat_history"]["status"] == "miss"
    assert sources["medical_metrics"]["count"] == 0
    assert sources["timeline"]["count"] == 0
    assert sources["chat_history"]["count"] == 0


def test_later_source_failure_does_not_erase_an_earlier_data_hit():
    summary = summarize_agent_chain(
        [
            _tool(
                "metrics-hit",
                "tool.read_medical_metrics",
                input={"names": ["CA15-3"]},
                output="CA15-3：18 U/mL",
            ),
            _tool(
                "metrics-failed",
                "tool.read_medical_metrics",
                input={"names": ["白细胞"]},
                output="网关超时",
                metadata={"ok": False},
            ),
        ]
    )

    source = next(
        item for item in summary["sources"] if item["key"] == "medical_metrics"
    )
    assert source["status"] == "hit"
    assert source["count"] == 1


def test_cx_agent_literature_audit_snapshot_keeps_raw_top_k_chunks_when_langfuse_is_truncated():
    chain = apply_literature_audit_snapshot(
        {
            "status": "synced",
            "nodes": [],
            "summary": summarize_agent_chain([]),
        },
        [
            {
                "id": "audit-1",
                "query": "乳腺癌 运动",
                "mode": "general",
                "rawHitCount": 2,
                "scorePassedCount": 1,
                "candidateSourceCount": 1,
                "selectedSourceCount": 1,
                "scoreThreshold": 0.65,
                "hits": [
                    {
                        "rank": 1,
                        "passedScore": True,
                        "selected": True,
                        "raw": {
                            "title": "乳腺癌运动指南",
                            "doi": "10.1/example",
                            "score": 0.91,
                            "content": "每周规律运动可改善生活质量。",
                        },
                    },
                    {
                        "rank": 2,
                        "passedScore": False,
                        "selected": False,
                        "raw": {
                            "title": "低分文献",
                            "score": 0.22,
                            "content": "这是被阈值过滤但仍应留档的 chunk。",
                        },
                    },
                ],
            }
        ],
    )

    rag = next(item for item in chain["summary"]["sources"] if item["key"] == "literature_rag")
    call = rag["rag_audit"][0]
    assert rag["status"] == "hit"
    assert call["all_sources"][1]["chunks"][0]["content"] == "这是被阈值过滤但仍应留档的 chunk。"
    assert call["selected_sources"][0]["doi"] == "10.1/example"
    assert call["candidate_sources"] == []
