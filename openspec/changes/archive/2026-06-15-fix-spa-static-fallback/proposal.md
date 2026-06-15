# Proposal: SPA 静态托管回退（fix-spa-static-fallback）

## Why

Docker / `serve_platform.sh` 单端口部署时，直接访问 `/runs` 等 React Router 路径会 404（`StaticFiles(html=True)` 不回退 `index.html`）。云主机无 Nginx 时同样受影响。

## What Changes

- `server/app.py`：Vite `assets/` 单独挂载；其余非 `/api` 路径先找静态文件，找不到则回 `index.html`。
- 路径穿越防护：`resolve()` + `relative_to(dist)`。
- 单测覆盖 `/runs`、`/assets/*`、`/api/health`。

## Non-Goals

- 不改 Nginx 示例（仍推荐 `try_files` 双保险）。
- 不改 Vite 构建配置。
