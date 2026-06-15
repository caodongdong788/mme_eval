## Context

平台基于 FastAPI + SQLAlchemy（SQLite 默认）+ React/Vite。当前无登录体系，导出对话流水
经 `lark-cli` 单一共享身份上传飞书。公司员工均用飞书，决定以飞书 OAuth2 作为平台登录，
并复用授权得到的 `user_access_token` 完成 per-user 导出。开发态：前端 `:5173` 经 vite 代理
把 `/api` 转发到后端 `:8000`，回调用前端同源地址以保证 cookie 同源。

## Goals / Non-Goals

**Goals:**
- 飞书 OAuth2 授权码登录，作为平台强制登录入口。
- per-user token 缓存 + 自动刷新；`refresh_token` 过期前免重新授权。
- 导出对话流水以当前登录用户身份直接调飞书 OpenAPI 上传。
- 未配密钥时 dev 放行，避免把使用者锁在外面。

**Non-Goals:**
- 细粒度角色/权限、租户隔离。
- token 加密存储（先标注后续加固项）。
- 改动 `medeval` CLI 评测的报告飞书发布链路（仍走 lark-cli）。

## Decisions

- **服务端会话 + httpOnly cookie（而非 JWT）**：token/敏感信息不进浏览器 JS，避免 XSS 泄露，
  且可服务端吊销。会话记录入 `session` 表，cookie 仅存随机 `session_id`。
- **OAuth2 授权码流程（authen/v2/oauth/token）**：飞书官方推荐，且只有该流程在开通
  `offline_access` 后返回 `refresh_token`，满足「免重新授权」。授权页用
  `accounts.feishu.cn/.../authorize`，换/刷新 token 用 `open.feishu.cn/.../oauth/token`。
- **state 防 CSRF**：login 时生成随机 state 暂存（短期会话/签名 cookie），callback 校验。
- **导出走 upload_all → import_tasks → 轮询**：与既有「在线表格」体验一致；以
  `user_access_token` 调用，文件夹 `mount_key` 取用户传入 token，空=个人根目录。
  替代方案「仅 upload_all 上传为可下载文件」更简单但不是在线表格，放弃。
- **`feishu_oauth` / `feishu_drive` 设计为无状态纯函数**：仅依赖入参与 httpx，便于 mock 单测。
- **`AUTH_REQUIRED` 由是否配置 `FEISHU_APP_ID` 推导**：避免本地无密钥时自锁。
- **token 自动刷新放在 `get_current_user` 依赖链**：访问受保护接口时若 access 临过期则刷新并
  回写 DB；refresh 过期则清会话、返回 401。

## Risks / Trade-offs

- [飞书后台未配置 redirect URI / scope] → callback 报错；在登录页给出明确指引文案与排错。
- [配齐密钥后强制登录可能临时阻断现有使用] → 用 `AUTH_REQUIRED` 推导 + 明确文档；
  本地未配密钥时维持放行。
- [token 明文入库（SQLite 本地）] → 标注为后续加固项；非目标内可选 `SESSION_SECRET` 同款
  对称加密后续补。
- [import_tasks 异步轮询超时] → 设最大轮询次数与超时，失败返回 502 + 原因。
- [cookie 跨端口/同源] → 开发回调用前端同源 `:5173`，cookie 落 localhost；CORS 已
  `allow_credentials`。

## Migration Plan

1. 配置飞书后台（redirect URI + scope），在 `.env` 填 `FEISHU_APP_ID/SECRET/REDIRECT_URI/SESSION_SECRET`。
2. 部署后端（建新表，SQLite 自动迁移/`init_db` 建表）。
3. 首次访问 → 飞书授权 → 登录成功。
4. 回滚：清空 `FEISHU_APP_ID`（或 `AUTH_REQUIRED=false`）即恢复匿名访问，新增表不影响旧逻辑。

## Open Questions

- 无（关键决策已确认：方案 A、强制登录、单实例起步按飞书 user 粒度天然隔离）。
