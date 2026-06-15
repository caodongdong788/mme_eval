## Why

平台当前无登录体系，导出对话流水到飞书统一走 `lark-cli` 的单一共享身份，不同员工
无法用各自飞书身份导出，且写死的 `parent_folder_token` 常因无权限而失败。公司员工
均使用飞书，故把飞书 OAuth 直接做成平台登录（SSO）：用户点一次授权，平台同时拿到
身份与带云空间权限的 token，并缓存复用、自动刷新，`refresh_token` 过期前无需重新授权。

## What Changes

- 新增飞书 OAuth2 授权码登录流程：授权跳转、回调换 token、取用户信息、建会话。
- 新增服务端会话（DB 持久化）+ httpOnly cookie；强制登录门禁（`get_current_user`）。
- 新增 per-user token 缓存与自动刷新（临过期用 `refresh_token` 续期；refresh 过期才重登）。
- 导出对话流水改为**以当前登录用户的 `user_access_token`** 直接调飞书 OpenAPI
  （`upload_all` → `import_tasks` → 轮询 ticket）上传，替换该端点中的 `lark-cli` 调用。
- 新增防自锁开关：未配置 `FEISHU_APP_ID` 时 `AUTH_REQUIRED=false`，守卫放行（dev 兜底）。
- 前端新增登录页、AuthContext、强制登录守卫与顶栏用户菜单。
- **BREAKING**（仅在配齐密钥后生效）：所有页面与 `/api/**` 业务接口需登录态。

## Capabilities

### New Capabilities
- `feishu-sso-auth`: 飞书 OAuth2 登录、会话管理、per-user token 缓存与自动刷新、强制登录门禁与 dev 兜底。

### Modified Capabilities
- `eval-platform-service`: 导出对话流水端点改为以当前登录用户的飞书 token 上传，不再依赖 `lark-cli` 共享身份。

## Impact

- 新增：`server/feishu_oauth.py`、`server/auth.py`、`server/routers/auth.py`、
  `server/feishu_drive.py`；`server/models_db.py` 增 `feishu_user` / `session` 两表；
  `server/settings.py` 增 OAuth/会话配置；`server/app.py` 挂登录路由与守卫；`.env.example`。
- 修改：`server/routers/runs.py` 导出端点；前端 `App`/路由、`api.ts`、新增 `LoginPage` 等。
- 依赖：复用现有 `httpx`；无新增第三方依赖（会话签名用标准库）。
- 外部前提：飞书开发者后台需配置 redirect URI 与 scope（`offline_access`、
  `contact:user.base:readonly`、`drive:drive`）。
