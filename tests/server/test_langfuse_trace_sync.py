from __future__ import annotations

import asyncio

import httpx

from medeval.models import ConversationTrace
from server.services.langfuse_trace import LangfuseTraceReader, sync_conversation_trace
from server.settings import Settings


def test_sync_conversation_trace_normalizes_v2_observations():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"].startswith("Basic ")
        if request.url.path == "/api/public/v2/observations":
            assert request.url.params["traceId"] == "trace-1"
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "agent-1",
                            "traceId": "trace-1",
                            "type": "AGENT",
                            "name": "agent-loop",
                            "startTime": "2026-07-21T08:00:00Z",
                            "endTime": "2026-07-21T08:00:01Z",
                            "input": '{"query":"乳房疼痛"}',
                            "output": {"answer": "请补充病史"},
                            "metadata": {"sampleId": "case-1"},
                        },
                        {
                            "id": "generation-1",
                            "traceId": "trace-1",
                            "parentObservationId": "agent-1",
                            "type": "GENERATION",
                            "name": "llm",
                            "startTime": "2026-07-21T08:00:00.100Z",
                            "endTime": "2026-07-21T08:00:00.600Z",
                            "providedModelName": "model-x",
                            "usageDetails": {"input": 10, "output": 5, "total": 15},
                        },
                    ]
                },
            )
        if request.url.path == "/api/public/traces/trace-1":
            return httpx.Response(
                200,
                json={"projectId": "project-1"},
            )
        return httpx.Response(404)

    settings = Settings(
        langfuse_host="https://langfuse.example",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
        langfuse_sync_attempts=1,
    )
    reader = LangfuseTraceReader(settings, transport=httpx.MockTransport(handler))
    trace = ConversationTrace(messages=[], langfuse_trace_ids=["trace-1"])

    snapshot = asyncio.run(sync_conversation_trace(trace, settings, reader=reader))
    asyncio.run(reader.close())

    assert snapshot["status"] == "synced"
    assert snapshot["traces"] == [
        {
            "trace_id": "trace-1",
            "trace_url": "https://langfuse.example/project/project-1/traces/trace-1",
        }
    ]
    assert snapshot["nodes"][0]["input"] == {"query": "乳房疼痛"}
    assert snapshot["nodes"][0]["duration_ms"] == 1000.0
    assert snapshot["nodes"][1]["parent_id"] == "agent-1"
    assert snapshot["nodes"][1]["usage"]["total"] == 15
    assert trace.langfuse_trace_url == snapshot["traces"][0]["trace_url"]
    assert len(requests) == 2


def test_sync_conversation_trace_is_fail_soft_when_not_configured():
    settings = Settings(langfuse_host="", langfuse_public_key="", langfuse_secret_key="")
    trace = ConversationTrace(messages=[], langfuse_trace_ids=["trace-1"])

    snapshot = asyncio.run(sync_conversation_trace(trace, settings))

    assert snapshot["status"] == "unconfigured"
    assert snapshot["trace_ids"] == ["trace-1"]
    assert snapshot["nodes"] == []


def test_reader_falls_back_to_v1_when_v2_has_ingestion_delay():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/api/public/v2/observations":
            return httpx.Response(200, json={"data": [], "meta": {"cursor": None}})
        if request.url.path == "/api/public/observations":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": "span-1",
                            "traceId": "trace-delayed",
                            "type": "SPAN",
                            "name": "tool-call",
                            "startTime": "2026-07-21T08:00:00Z",
                        }
                    ]
                },
            )
        if request.url.path == "/api/public/traces/trace-delayed":
            return httpx.Response(200, json={})
        return httpx.Response(404)

    settings = Settings(
        langfuse_host="https://langfuse.example",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
        langfuse_sync_attempts=1,
    )
    reader = LangfuseTraceReader(settings, transport=httpx.MockTransport(handler))
    result = asyncio.run(reader.fetch_trace("trace-delayed"))
    asyncio.run(reader.close())

    assert result["nodes"][0]["name"] == "tool-call"
    assert paths[:2] == [
        "/api/public/v2/observations",
        "/api/public/observations",
    ]


def test_sync_marks_not_yet_ingested_trace_as_pending():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path in {"/api/public/v2/observations", "/api/public/observations"}:
            return httpx.Response(200, json={"data": []})
        return httpx.Response(404)

    settings = Settings(
        langfuse_host="https://langfuse.example",
        langfuse_public_key="pk-test",
        langfuse_secret_key="sk-test",
        langfuse_sync_attempts=1,
    )
    reader = LangfuseTraceReader(settings, transport=httpx.MockTransport(handler))
    trace = ConversationTrace(messages=[], langfuse_trace_ids=["trace-delayed"])

    snapshot = asyncio.run(sync_conversation_trace(trace, settings, reader=reader))
    asyncio.run(reader.close())

    assert snapshot["status"] == "pending"
    assert snapshot["nodes"] == []
    assert "暂未写入完成" in snapshot["error"]
