"""生产环境 SPA 静态托管（Vite dist + index.html 回退）。"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

logger = logging.getLogger("mme.server")


def install_frontend_spa(app: FastAPI, dist: Path) -> None:
    """托管 ``frontend/dist``：``/assets`` 走 StaticFiles，其余非 API 路径回退 ``index.html``。"""
    dist = dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        logger.warning("frontend/dist 存在但缺少 index.html，跳过 SPA 托管")
        return

    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(assets_dir)),
            name="frontend-assets",
        )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path:
            candidate = (dist / full_path).resolve()
            try:
                candidate.relative_to(dist)
            except ValueError as exc:
                raise HTTPException(status_code=404, detail="Not Found") from exc
            if candidate.is_file():
                return FileResponse(candidate)
        return FileResponse(index)
