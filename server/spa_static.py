"""生产环境 SPA 静态托管（Vite dist + index.html 回退）。"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.staticfiles import StaticFiles

logger = logging.getLogger("mme.server")

# Vite 会为 JS/CSS 使用内容哈希文件名，因此可以长期缓存；但 index.html 是入口清单，
# 发布后必须重新校验，避免旧入口动态 import 已被替换的 chunk。
# `app` 容器重建时会整体替换 dist。即便资源文件名带 hash，旧浏览器标签页中
# 的入口脚本仍可能引用上一版的懒加载 chunk；如果浏览器直接复用旧资源缓存，
# 该 chunk 在新容器中已经不存在，就会出现 "Failed to fetch dynamically
# imported module"。因此所有 SPA 静态资源都需要在使用前重新校验。
SPA_NO_CACHE_HEADERS = {"Cache-Control": "no-cache"}


class _RevalidatingStaticFiles(StaticFiles):
    """静态资源可缓存，但每次使用前必须向当前发布版本重新校验。"""

    async def get_response(self, path: str, scope: object):  # type: ignore[override]
        response = await super().get_response(path, scope)  # type: ignore[arg-type]
        response.headers.update(SPA_NO_CACHE_HEADERS)
        return response


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
            _RevalidatingStaticFiles(directory=str(assets_dir)),
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
                if candidate == index:
                    return FileResponse(index, headers=SPA_NO_CACHE_HEADERS)
                return FileResponse(candidate, headers=SPA_NO_CACHE_HEADERS)
        return FileResponse(index, headers=SPA_NO_CACHE_HEADERS)
