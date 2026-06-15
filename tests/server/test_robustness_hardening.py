"""B2 工程健壮性：全局异常兜底、deps.creator_name、job runner 优雅关闭。"""

from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.app import create_app
from server.deps import creator_name
from server.jobs import InProcessJobRunner


def test_global_exception_handler_returns_500_json(initialized_db):
    app: FastAPI = create_app()

    @app.get("/api/_boom")
    def _boom() -> dict:
        raise RuntimeError("kaboom")

    # 生产托管时根挂了 StaticFiles("/") 会先匹配；把新增测试路由提到最前，确保命中。
    app.router.routes.insert(0, app.router.routes.pop())

    # raise_server_exceptions=False 让 TestClient 不重抛，验证兜底响应体形状。
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/api/_boom")
    assert resp.status_code == 500
    body = resp.json()
    assert "detail" in body
    # 开发态（默认非生产）应暴露异常类型，便于排障。
    assert "RuntimeError" in body["detail"]


def test_creator_name_handles_none():
    assert creator_name(None) is None


def test_job_runner_shutdown_cancels_inflight():
    async def _scenario() -> None:
        runner = InProcessJobRunner(max_concurrent=1)

        async def _never_ending(_progress) -> None:
            await asyncio.sleep(3600)

        await runner.submit(run_id=999, job=_never_ending)
        await asyncio.sleep(0)  # 让任务起跑
        await runner.shutdown()  # 不应卡死/抛出
        assert all(t.done() for t in runner._tasks.values())

    asyncio.run(_scenario())
