from __future__ import annotations

from server.services.agent_chain_summary import (
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
                "nodes": [_tool("timeline", "tool.read_timeline", input={"keys": ["复查"]})],
            }
        }
    }

    hydrated = ensure_agent_chain_summary(detail)

    assert "summary" not in detail["trace"]["agent_chain"]
    assert hydrated["trace"]["agent_chain"]["summary"]["sources"][2]["status"] == "queried"
