"""FastAPI 应用入口。

``create_app()`` 构造应用：启动时建表、挂载 API 路由、（若存在）静态托管前端构建产物。
开发时：``uvicorn server.app:app --reload``（前端用 Vite dev server + 代理）。
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .db import init_db, session_scope
from .settings import get_settings
from .spa_static import install_frontend_spa

logger = logging.getLogger("mme.server")

# 强制登录豁免：健康检查与认证流程本身。
_AUTH_EXEMPT_PREFIXES = ("/api/health", "/api/auth/")


def _configure_logging() -> None:
    """统一日志：root 未配 handler 时按 ``MEDEVAL_LOG_LEVEL``（默认 INFO）初始化。

    幂等——已有 handler（如被 uvicorn/测试框架接管）则不重复配置，避免双写。
    """
    if logging.getLogger().handlers:
        return
    level = os.environ.get("MEDEVAL_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@asynccontextmanager
async def _lifespan(app: FastAPI):
    _configure_logging()
    # 生产环境安全前置校验（默认密钥禁止上线）；dev/test 始终通过。
    get_settings().check_production_security()
    init_db()
    # 回收孤儿任务：进程重启后内存任务态丢失，DB 中残留的 running/pending 置为 failed。
    from .jobs import reconcile_orphaned_runs
    from .pairwise_job import reconcile_orphaned_pairwise

    n_runs = reconcile_orphaned_runs()
    n_pair = reconcile_orphaned_pairwise()
    logger.info("启动完成：回收孤儿评测 %s 条、孤儿对战 %s 条", n_runs, n_pair)
    try:
        yield
    finally:
        # 优雅关闭：取消在跑评测任务，等待其结束（残留状态由下次启动 reconcile 回收）。
        from .jobs import get_job_runner

        try:
            await get_job_runner().shutdown()
            logger.info("已优雅关闭：在跑评测任务已取消")
        except Exception:  # noqa: BLE001 —— 关闭阶段不再抛出
            logger.warning("关闭阶段取消任务出错", exc_info=True)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="MME · Agent 评测平台", version="0.1.0", lifespan=_lifespan)

    # 本地开发：允许 Vite dev server 跨域。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 全局异常兜底：未被各路由捕获的异常统一记录并返回 500（生产隐藏堆栈细节）。
    @app.exception_handler(Exception)
    async def _unhandled_exc(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常 %s %s", request.method, request.url.path)
        detail = (
            "服务器内部错误，请稍后重试"
            if get_settings().is_production
            else f"{type(exc).__name__}: {exc}"
        )
        return JSONResponse(status_code=500, content={"detail": detail})

    # 强制登录守卫：仅当配置了飞书应用密钥（auth_required）时生效；未配则放行（dev 兜底）。
    @app.middleware("http")
    async def _auth_guard(request: Request, call_next):
        settings = get_settings()
        path = request.url.path
        if (
            settings.auth_required
            and request.method != "OPTIONS"
            and path.startswith("/api/")
            and not path.startswith(_AUTH_EXEMPT_PREFIXES)
        ):
            from .auth import SESSION_COOKIE, resolve_session

            sid = request.cookies.get(SESSION_COOKIE, "")
            with session_scope() as s:
                user = resolve_session(s, sid)
            if user is None:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "未登录或会话已过期，请用飞书登录"},
                )
        return await call_next(request)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    # API 路由
    from .routers import (
        auth,
        benchmarks,
        cases,
        compare,
        config,
        dashboard,
        judge_models,
        runs,
    )

    app.include_router(auth.router)
    app.include_router(benchmarks.router)
    app.include_router(runs.router)
    app.include_router(dashboard.router)
    app.include_router(cases.router)
    app.include_router(config.router)
    app.include_router(judge_models.router)
    app.include_router(compare.router)

    # 生产：托管前端构建产物（frontend/dist）。开发时不存在则跳过。
    dist = settings.project_root / "frontend" / "dist"
    if dist.is_dir():
        install_frontend_spa(app, dist)

    return app


app = create_app()
