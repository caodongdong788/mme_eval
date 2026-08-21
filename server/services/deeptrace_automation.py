"""将 Open API 发起的 Agent 评测结果回写至 DeepTrace。

DeepTrace 执行记录由调用方先创建，MME 只在正式评测成功后 PATCH 最终统计。
回写失败不会改变 MME 的评测结果，状态仅作为运行元数据保存，便于排查与重试。
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import case, func, select

from ..db import session_scope
from ..models_db import CaseResultRow, EvalRun
from ..settings import Settings, get_settings

logger = logging.getLogger(__name__)
_SHANGHAI = ZoneInfo("Asia/Shanghai")


def _executed_at(value: datetime | None) -> str:
    """将数据库 UTC naive 时间转换为 DeepTrace 所需的带时区 ISO 时间。"""
    instant = value or datetime.now(timezone.utc).replace(tzinfo=None)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(_SHANGHAI).isoformat(timespec="seconds")


def _prepare_completion_payload(run_id: int, settings: Settings) -> tuple[str, dict[str, Any]] | None:
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        if run is None or run.status != "success" or run.trigger_type != "open_api":
            return None
        integration = (run.adapter_overrides or {}).get("deeptrace")
        execution_id = str(integration.get("execution_id") or "").strip() if isinstance(integration, dict) else ""
        if not execution_id:
            return None
        total, passed = session.execute(
            select(
                func.count(CaseResultRow.id),
                func.coalesce(
                    func.sum(case((CaseResultRow.release_passed.is_(True), 1), else_=0)),
                    0,
                ),
            ).where(CaseResultRow.run_id == run_id)
        ).one()
        total_cases = int(total or 0)
        passed_cases = int(passed or 0)
        return execution_id, {
            "totalCases": total_cases,
            "passedCases": passed_cases,
            "failedCases": total_cases - passed_cases,
            # MME 的 release_passed 代表通过与否，不对研发缺陷做归类，保持 0。
            "bugsFound": 0,
            "reportUrl": f"{settings.frontend_url.rstrip('/')}/runs/{run.id}",
            "executedAt": _executed_at(run.finished_at),
        }


def _record_sync_state(run_id: int, *, status: str, error: str = "") -> None:
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        if run is None:
            return
        overrides = dict(run.adapter_overrides or {})
        integration = dict(overrides.get("deeptrace") or {})
        if not integration.get("execution_id"):
            return
        integration.update(
            {
                "last_sync_status": status,
                "last_synced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "last_error": error[:1000],
            }
        )
        overrides["deeptrace"] = integration
        run.adapter_overrides = overrides


async def report_run_completion(
    run_id: int,
    settings: Settings | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> bool:
    """PATCH 已关联的 DeepTrace 执行记录；外部失败不影响 MME 成功状态。"""
    settings = settings or get_settings()
    prepared = _prepare_completion_payload(run_id, settings)
    if prepared is None:
        return False
    execution_id, payload = prepared
    token = settings.deeptrace_open_api_token.strip()
    space_key = settings.deeptrace_space_key.strip()
    if not token or not space_key:
        logger.warning("DeepTrace 回写未配置 run_id=%s execution_id=%s", run_id, execution_id)
        _record_sync_state(run_id, status="skipped", error="DeepTrace 回写未配置")
        return False
    base_url = settings.deeptrace_base_url.rstrip("/")
    url = (
        f"{base_url}/api/open/v1/spaces/{quote(space_key, safe='')}/"
        f"automation-test-runs/{quote(execution_id, safe='')}"
    )
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.deeptrace_timeout_seconds)
    try:
        response = await client.patch(
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        response.raise_for_status()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("DeepTrace 回写失败 run_id=%s execution_id=%s", run_id, execution_id, exc_info=True)
        _record_sync_state(run_id, status="failed", error=str(exc))
        return False
    finally:
        if owns_client:
            await client.aclose()
    _record_sync_state(run_id, status="success")
    logger.info("DeepTrace 回写成功 run_id=%s execution_id=%s", run_id, execution_id)
    return True
