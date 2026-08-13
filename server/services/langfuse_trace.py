"""把 cx-agent 内部 Langfuse observations 固化为 Case 可展示的调用链快照。"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select

from medeval.models import ConversationTrace, RunReport

from ..db import session_scope
from ..models_db import CaseResultRow
from ..settings import Settings
from .agent_chain_summary import apply_literature_audit_snapshot, summarize_agent_chain
from .case_query import case_rag_status_from_detail


_FIELDS = "core,basic,time,io,metadata,model,usage,prompt,metrics,trace_context"
logger = logging.getLogger(__name__)

# 后台任务需保留强引用，避免在还未执行时被垃圾回收。服务关闭时事件循环会统一取消。
_post_run_backfill_tasks: set[asyncio.Task[dict[str, int]]] = set()


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
                # Langfuse 的异步 ingest 在 cx-agent 请求刚结束时可能仍未可读。
                # 退避上限控制在 8 秒，避免单条链路无限拖慢评测收尾。
                initial = max(0.0, self.settings.langfuse_sync_initial_backoff_seconds)
                await asyncio.sleep(min(8.0, initial * (2**attempt)))
        if last_error is not None:
            raise last_error
        raise RuntimeError("Langfuse trace 暂未写入完成")


async def sync_conversation_trace(
    trace: ConversationTrace,
    settings: Settings,
    *,
    reader: LangfuseTraceReader | None = None,
) -> dict[str, Any]:
    def store_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
        trace.agent_chain = apply_literature_audit_snapshot(
            snapshot,
            trace.cx_literature_audits,
        )
        return trace.agent_chain

    trace_ids = list(dict.fromkeys(trace.langfuse_trace_ids))
    if not trace_ids:
        return store_snapshot(trace.agent_chain)

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
        store_snapshot(snapshot)
        if owned_reader:
            await reader.close()
        return trace.agent_chain

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
        # 读空通常不代表调用或凭据失败，而是 Langfuse 尚未完成异步写入。
        # 单独标为 pending，前端会在打开用例时自动补同步一次。
        all_pending = bool(errors) and all("Langfuse trace 暂未写入完成" in error for error in errors)
        snapshot = {
            "status": (
                "synced"
                if not errors
                else "partial"
                if traces
                else "pending"
                if all_pending
                else "failed"
            ),
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "trace_ids": trace_ids,
            "traces": [
                {key: value for key, value in item.items() if key != "nodes"}
                for item in traces
            ],
            "nodes": nodes,
            "summary": summarize_agent_chain(nodes),
            "error": "；".join(errors) if errors else None,
        }
        return store_snapshot(snapshot)
    finally:
        if owned_reader:
            await reader.close()


async def enrich_report_agent_chains(report: RunReport, settings: Settings) -> None:
    reader = LangfuseTraceReader(settings)
    try:
        semaphore = asyncio.Semaphore(4)

        async def sync_one(trace: ConversationTrace) -> None:
            async with semaphore:
                await sync_conversation_trace(trace, settings, reader=reader)

        await asyncio.gather(*(sync_one(result.trace) for result in report.results))
    finally:
        await reader.close()


def _needs_agent_chain_backfill(detail: dict[str, Any]) -> bool:
    trace = _record(detail.get("trace"))
    trace_ids = trace.get("langfuse_trace_ids")
    if not isinstance(trace_ids, list) or not any(isinstance(item, str) and item for item in trace_ids):
        return False
    chain = _record(trace.get("agent_chain"))
    # 已确认同步完成或明确未配置时无需再请求。partial/failed/pending 均可能是
    # Langfuse 入库窗口造成的临时状态，允许后台重试。
    return str(chain.get("status") or "") not in {"synced", "unconfigured"}


def _load_backfill_candidates(run_id: int) -> list[tuple[int, dict[str, Any]]]:
    with session_scope() as session:
        rows = session.execute(
            select(CaseResultRow.id, CaseResultRow.detail_json).where(
                CaseResultRow.run_id == run_id
            )
        ).all()
    candidates: list[tuple[int, dict[str, Any]]] = []
    for row_id, raw_detail in rows:
        detail = dict(raw_detail or {})
        if _needs_agent_chain_backfill(detail):
            candidates.append((int(row_id), detail))
    return candidates


def _persist_backfill_snapshots(
    snapshots: list[tuple[int, dict[str, Any]]],
) -> int:
    updated = 0
    with session_scope() as session:
        for row_id, detail in snapshots:
            row = session.get(CaseResultRow, row_id)
            # 用户在此期间手动同步成功时，不能用旧快照覆盖新数据。
            if row is None or not _needs_agent_chain_backfill(dict(row.detail_json or {})):
                continue
            row.detail_json = detail
            row.rag_status = case_rag_status_from_detail(detail)
            updated += 1
    return updated


async def backfill_run_agent_chains(
    run_id: int,
    settings: Settings,
    *,
    delay_seconds: float | None = None,
    attempts: int | None = None,
) -> dict[str, int]:
    """在评测成功后补拉尚未写入 Langfuse 的 Case 调用链并回填列表状态。

    这条链路不参与判分，也不阻塞评测任务完成；它只修正 observability 快照和
    ``rag_status``。每轮仅查询尚未同步的 Case，成功后自然停止。
    """
    delay = max(
        0.0,
        settings.langfuse_post_run_sync_delay_seconds
        if delay_seconds is None
        else delay_seconds,
    )
    rounds = max(
        1,
        settings.langfuse_post_run_sync_attempts if attempts is None else attempts,
    )
    summary = {"eligible": 0, "updated": 0, "rounds": 0}
    reader = LangfuseTraceReader(settings)
    if not reader.configured:
        await reader.close()
        return summary

    try:
        for index in range(rounds):
            if delay:
                await asyncio.sleep(delay)
            candidates = _load_backfill_candidates(run_id)
            if not candidates:
                break
            summary["eligible"] += len(candidates)
            summary["rounds"] += 1
            semaphore = asyncio.Semaphore(4)

            async def sync_one(row_id: int, detail: dict[str, Any]) -> tuple[int, dict[str, Any]] | None:
                try:
                    trace = ConversationTrace.model_validate(
                        _record(detail.get("trace")) or {"messages": []}
                    )
                    async with semaphore:
                        await sync_conversation_trace(trace, settings, reader=reader)
                    next_detail = dict(detail)
                    next_detail["trace"] = trace.model_dump(mode="json")
                    return row_id, next_detail
                except Exception:  # noqa: BLE001 - 后台观测补偿绝不影响评测结果
                    logger.warning("run %s case %s Langfuse 补同步失败", run_id, row_id, exc_info=True)
                    return None

            results = await asyncio.gather(
                *(sync_one(row_id, detail) for row_id, detail in candidates)
            )
            snapshots = [item for item in results if item is not None]
            summary["updated"] += _persist_backfill_snapshots(snapshots)
    finally:
        await reader.close()
    return summary


def schedule_run_agent_chain_backfill(run_id: int, settings: Settings) -> asyncio.Task[dict[str, int]] | None:
    """提交非阻塞的 Langfuse 延迟补同步任务；未配置时不创建空任务。"""
    if not (
        settings.langfuse_host
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    ):
        return None
    task = asyncio.create_task(
        backfill_run_agent_chains(run_id, settings),
        name=f"mme-langfuse-backfill-{run_id}",
    )
    _post_run_backfill_tasks.add(task)

    def done(completed: asyncio.Task[dict[str, int]]) -> None:
        _post_run_backfill_tasks.discard(completed)
        if completed.cancelled():
            return
        try:
            completed.result()
        except Exception:  # noqa: BLE001 - 后台观测任务绝不影响已成功评测
            logger.warning("run %s Langfuse 后台补同步失败", run_id, exc_info=True)

    task.add_done_callback(done)
    return task
