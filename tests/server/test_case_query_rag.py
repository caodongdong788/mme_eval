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


def test_rag_status_prefers_cx_agent_audit_when_langfuse_is_not_synced():
    detail = {
        "trace": {
            "cx_literature_audits": [{"selectedSourceCount": 2}],
            "agent_chain": {
                "status": "synced",
                "summary": {
                    "sources": [
                        {"key": "literature_rag", "calls": 0, "status": "unused"}
                    ]
                },
            },
        }
    }
    assert case_rag_status(row(detail)) == "hit"


def test_rag_status_uses_audit_snapshot_for_empty_retrieval():
    detail = {"trace": {"cx_literature_audits": [{"selectedSourceCount": 0}]}}
    assert case_rag_status(row(detail)) == "miss"


def test_rag_status_marks_successful_empty_audit_as_not_triggered():
    detail = {
        "trace": {
            "cx_literature_audits": [],
            "cx_literature_audit_fetched": True,
        }
    }
    assert case_rag_status(row(detail)) == "not_triggered"


def test_rag_status_handles_legacy_cx_empty_audit_as_not_triggered():
    detail = {
        "trace": {
            "cx_literature_audits": [],
            "cx_literature_audit_error": None,
            "evaluation_identity": {"cx_session_id": "cx-session-1"},
        }
    }
    assert case_rag_status(row(detail)) == "not_triggered"
