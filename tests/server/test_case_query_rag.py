from types import SimpleNamespace

from server.services.case_query import case_rag_status


def row(detail_json):
    return SimpleNamespace(detail_json=detail_json)


def test_rag_status_uses_actual_literature_tool_summary():
    detail = {
        "trace": {
            "agent_chain": {
                "status": "synced",
                "summary": {
                    "sources": [
                        {"key": "literature_rag", "calls": 1, "status": "hit"}
                    ]
                },
            }
        }
    }
    assert case_rag_status(row(detail)) == "hit"


def test_rag_status_distinguishes_not_triggered_from_unsynced():
    synced = {
        "trace": {
            "agent_chain": {
                "status": "synced",
                "summary": {
                    "sources": [
                        {"key": "literature_rag", "calls": 0, "status": "unused"}
                    ]
                },
            }
        }
    }
    assert case_rag_status(row(synced)) == "not_triggered"
    assert case_rag_status(row({"trace": {"agent_chain": {"status": "pending"}}})) == "unknown"
