"""把 cx-agent 内部 Langfuse observations 固化为 Case 可展示的调用链快照。"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import httpx

from medeval.models import ConversationTrace, RunReport

from ..settings import Settings


_FIELDS = "core,basic,time,io,metadata,model,usage,prompt,metrics,trace_context"


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


def _first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] is not None:
            return row[key]
    return None


def _duration_ms(start: Any, end: Any, latency: Any) -> float | None:
    if isinstance(latency, (int, float)):
        return round(float(latency) * 1000, 2)
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    try:
        started = datetime.fromisoformat(start.replace("Z", "+00:00"))
        finished = datetime.fromisoformat(end.replace("Z", "+00:00"))
        return round((finished - started).total_seconds() * 1000, 2)
    except ValueError:
        return None


def _time_sort_key(value: Any) -> float:
    if not isinstance(value, str):
        return float("inf")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return float("inf")


def normalize_observation(row: dict[str, Any]) -> dict[str, Any]:
    """兼容 Langfuse v1/v2 字段名，输出稳定的前端节点结构。"""
    usage = _record(_first(row, "usageDetails", "usage"))
    start = _first(row, "startTime", "start_time")
    end = _first(row, "endTime", "end_time")
    node = {
        "id": str(_first(row, "id") or ""),
        "trace_id": str(_first(row, "traceId", "trace_id") or ""),
        "parent_id": _first(row, "parentObservationId", "parent_observation_id"),
        "type": str(_first(row, "type") or "SPAN").upper(),
        "name": str(_first(row, "name") or "未命名节点"),
        "start_time": start,
        "end_time": end,
        "duration_ms": _duration_ms(start, end, _first(row, "latency")),
        "level": _first(row, "level"),
        "status_message": _first(row, "statusMessage", "status_message"),
        "model": _first(row, "providedModelName", "model", "internalModelId"),
        "input": _json_value(_first(row, "input")),
        "output": _json_value(_first(row, "output")),
        "metadata": _record(_json_value(_first(row, "metadata"))),
        "usage": usage,
        "prompt": {
            "name": _first(row, "promptName"),
            "version": _first(row, "promptVersion"),
        },
    }
    return node


class LangfuseTraceReader:
    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.host = settings.langfuse_host.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=settings.langfuse_sync_timeout_seconds,
            auth=(settings.langfuse_public_key, settings.langfuse_secret_key),
            transport=transport,
        )

    @property
    def configured(self) -> bool:
        return bool(
            self.host
            and self.settings.langfuse_public_key
            and self.settings.langfuse_secret_key
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def _v2_observations(self, trace_id: str) -> list[dict[str, Any]] | None:
        response = await self._client.get(
            f"{self.host}/api/public/v2/observations",
            params={
                "traceId": trace_id,
                "fields": _FIELDS,
                "parseIoAsJson": "true",
                "limit": 1000,
            },
        )
        if response.status_code in (400, 404, 405):
            return None
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", []) if isinstance(payload, dict) else payload
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    async def _v1_observations(self, trace_id: str) -> list[dict[str, Any]]:
        response = await self._client.get(
            f"{self.host}/api/public/observations",
            params={"traceId": trace_id, "limit": 100},
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", []) if isinstance(payload, dict) else payload
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    async def _trace_info(self, trace_id: str) -> dict[str, Any]:
        response = await self._client.get(f"{self.host}/api/public/traces/{trace_id}")
        if response.status_code == 404:
            return {}
        response.raise_for_status()
        return _record(response.json())

    def _trace_url(self, trace_id: str, info: dict[str, Any], nodes: list[dict[str, Any]]) -> str | None:
        html_path = _first(info, "htmlPath", "html_path")
        if isinstance(html_path, str) and html_path:
            return html_path if html_path.startswith("http") else f"{self.host}{html_path}"
        project_id = _first(info, "projectId", "project_id")
        if not project_id and nodes:
            project_id = _first(nodes[0], "projectId", "project_id")
        if project_id:
            return f"{self.host}/project/{project_id}/traces/{trace_id}"
        return None

    async def fetch_trace(self, trace_id: str) -> dict[str, Any]:
        last_error: Exception | None = None
        attempts = max(1, self.settings.langfuse_sync_attempts)
        for attempt in range(attempts):
            try:
                rows = await self._v2_observations(trace_id)
                # cx-agent 当前 Langfuse JS SDK 5.3 写入 v2 可能有分钟级延迟；
                # v2 不支持或暂时为空时，用 v1 读取刚完成的 trace。
                if not rows:
                    rows = await self._v1_observations(trace_id)
                if rows:
                    info = await self._trace_info(trace_id)
                    nodes = [normalize_observation(row) for row in rows]
                    nodes.sort(key=lambda item: _time_sort_key(item.get("start_time")))
                    return {
                        "trace_id": trace_id,
                        "trace_url": self._trace_url(trace_id, info, rows),
                        "nodes": nodes,
                    }
            except Exception as exc:  # noqa: BLE001 - observability is fail-soft
                last_error = exc
            if attempt + 1 < attempts:
                await asyncio.sleep(0.5 * (2**attempt))
        if last_error is not None:
            raise last_error
        raise RuntimeError("Langfuse trace 暂未写入完成")


async def sync_conversation_trace(
    trace: ConversationTrace,
    settings: Settings,
    *,
    reader: LangfuseTraceReader | None = None,
) -> dict[str, Any]:
    trace_ids = list(dict.fromkeys(trace.langfuse_trace_ids))
    if not trace_ids:
        return trace.agent_chain

    owned_reader = reader is None
    reader = reader or LangfuseTraceReader(settings)
    if not reader.configured:
        snapshot = {
            "status": "unconfigured",
            "trace_ids": trace_ids,
            "traces": [],
            "nodes": [],
            "error": "Langfuse 读取凭据未配置",
        }
        trace.agent_chain = snapshot
        if owned_reader:
            await reader.close()
        return snapshot

    try:
        results = await asyncio.gather(
            *(reader.fetch_trace(trace_id) for trace_id in trace_ids),
            return_exceptions=True,
        )
        traces: list[dict[str, Any]] = []
        errors: list[str] = []
        for trace_id, result in zip(trace_ids, results):
            if isinstance(result, BaseException):
                errors.append(f"{trace_id}: {result}")
            else:
                traces.append(result)
        nodes = [node for item in traces for node in item.get("nodes", [])]
        nodes.sort(key=lambda item: _time_sort_key(item.get("start_time")))
        first_url = next((item.get("trace_url") for item in traces if item.get("trace_url")), None)
        if first_url and not trace.langfuse_trace_url:
            trace.langfuse_trace_url = str(first_url)
        snapshot = {
            "status": "synced" if not errors else "partial" if traces else "failed",
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "trace_ids": trace_ids,
            "traces": [
                {key: value for key, value in item.items() if key != "nodes"}
                for item in traces
            ],
            "nodes": nodes,
            "error": "；".join(errors) if errors else None,
        }
        trace.agent_chain = snapshot
        return snapshot
    finally:
        if owned_reader:
            await reader.close()


async def enrich_report_agent_chains(report: RunReport, settings: Settings) -> None:
    reader = LangfuseTraceReader(settings)
    try:
        semaphore = asyncio.Semaphore(4)

        async def sync_one(trace: ConversationTrace) -> None:
            if not trace.langfuse_trace_ids:
                return
            async with semaphore:
                await sync_conversation_trace(trace, settings, reader=reader)

        await asyncio.gather(*(sync_one(result.trace) for result in report.results))
    finally:
        await reader.close()
