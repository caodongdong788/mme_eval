"""启动回收孤儿评测任务：running/pending→failed，success 不动，幂等。"""

from __future__ import annotations

from sqlalchemy import select

from server.db import session_scope
from server.jobs import reconcile_orphaned_runs
from server.models_db import EvalRun


def _seed(status: str) -> int:
    with session_scope() as s:
        row = EvalRun(run_slug=f"r_{status}", name=status, status=status)
        s.add(row)
        s.flush()
        return row.id


def test_reconcile_marks_running_and_pending_failed(initialized_db):
    rid_run = _seed("running")
    rid_pend = _seed("pending")
    rid_ok = _seed("success")

    n = reconcile_orphaned_runs()
    assert n == 2

    with session_scope() as s:
        running = s.get(EvalRun, rid_run)
        pending = s.get(EvalRun, rid_pend)
        ok = s.get(EvalRun, rid_ok)
        assert running.status == "failed" and running.error_msg
        assert running.finished_at is not None
        assert pending.status == "failed" and pending.error_msg
        assert ok.status == "success"  # 成功记录不动


def test_reconcile_is_idempotent(initialized_db):
    _seed("running")
    assert reconcile_orphaned_runs() == 1
    assert reconcile_orphaned_runs() == 0  # 二次无可回收


def test_reconciled_run_is_deletable(client, initialized_db):
    rid = _seed("running")
    reconcile_orphaned_runs()
    # 回收后非 running/pending → 可删除
    assert client.delete(f"/api/runs/{rid}").status_code == 204
    with session_scope() as s:
        assert s.execute(select(EvalRun).where(EvalRun.id == rid)).scalar_one_or_none() is None
