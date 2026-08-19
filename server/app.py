"""FastAPI 应用入口。

``create_app()`` 构造应用：启动时建表、挂载 API 路由、（若存在）静态托管前端构建产物。
开发时：``uvicorn server.app:app --reload``（前端用 Vite dev server + 代理）。
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .db import init_db, session_scope
from .error_messages import format_validation_errors, humanize_error_text
from .settings import get_settings
from .spa_static import install_frontend_spa

logger = logging.getLogger("mme.server")

# 强制登录豁免：健康检查与认证流程本身。
_AUTH_EXEMPT_PREFIXES = ("/api/health", "/api/auth/", "/api/open/")


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
    # 注册可直接选择的默认模型；密钥仅保留在运行环境的 LLM_API_KEY 中。
    from .services.default_judge_model import ensure_default_judge_model

    with session_scope() as session:
        ensure_default_judge_model(session, get_settings())
    # 进程内兼容模式仍需回收孤儿任务；数据库队列模式由 Worker 租约自动接管，绝不能
    # 因 Web 服务部署就把正在执行的评测标记为失败。
    from .jobs import reconcile_orphaned_runs
    from .pairwise_job import reconcile_orphaned_pairwise

    if get_settings().job_runner_mode == "database":
        from .durable_queue import reconcile_succeeded_run_statuses, reconcile_unqueued_runs

        n_recovered, n_unrecoverable = reconcile_unqueued_runs(get_settings())
        n_status_repaired = reconcile_succeeded_run_statuses()
        n_runs = 0
        logger.info(
            "持久化队列校准：恢复 %s 条、缺少断点失败 %s 条、成功状态回填 %s 条",
            n_recovered,
            n_unrecoverable,
            n_status_repaired,
        )
    else:
        n_runs = reconcile_orphaned_runs()
    n_pair = reconcile_orphaned_pairwise()
    logger.info("启动完成：回收孤儿评测 %s 条、孤儿对战 %s 条", n_runs, n_pair)
    from .services.scheduled_evaluations import start_scheduler, stop_scheduler
    from .services.attribution_tasks import (
        reconcile_orphaned_attribution_tasks,
        stop_attribution_tasks,
    )

    start_scheduler()
    n_attribution = reconcile_orphaned_attribution_tasks()
    if n_attribution:
        logger.info("启动完成：回收中断归因任务 %s 条", n_attribution)
    try:
        yield
    finally:
        await stop_scheduler()
        await stop_attribution_tasks()
        # 数据库模式这里只关闭无状态调度器；评测由独立 Worker 持续执行。
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

    @app.exception_handler(RequestValidationError)
    async def _request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.info("请求参数校验失败 %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=422,
            content={
                "detail": format_validation_errors(
                    exc.errors(), prefix="请求参数校验失败"
                )
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        if isinstance(detail, str):
            detail = humanize_error_text(detail, fallback="请求处理失败，请检查后重试")
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": detail},
            headers=exc.headers,
        )

    # 全局异常兜底：未被各路由捕获的异常统一记录并返回 500（生产隐藏堆栈细节）。
    @app.exception_handler(Exception)
    async def _unhandled_exc(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常 %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "服务器处理请求时发生异常，请稍后重试；如持续出现，请联系管理员"},
        )

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
        calibration,
        compare,
        config,
        dashboard,
        judge_models,
        open_api,
        runs,
        scheduled_evaluations,
    )

    app.include_router(auth.router)
    app.include_router(benchmarks.router)
    app.include_router(runs.router)
    app.include_router(calibration.router)
    app.include_router(dashboard.router)
    app.include_router(config.router)
    app.include_router(judge_models.router)
    app.include_router(compare.router)
    app.include_router(open_api.router)
    app.include_router(scheduled_evaluations.router)

    # 生产：托管前端构建产物（frontend/dist）。开发时不存在则跳过。
    dist = settings.project_root / "frontend" / "dist"
    if dist.is_dir():
        install_frontend_spa(app, dist)

    return app


app = create_app()
