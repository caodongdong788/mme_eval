# 设计文档：飞书 SSO 登录 + per-user token 缓存复用

- 日期：2026-06-03
- 状态：已与用户确认（方案 A）
- 关联 OpenSpec change：`add-feishu-sso-auth`

## 1. 背景与目标

平台当前无登录/账号体系（auth 仅预留）。导出对话流水到飞书时统一走 `lark-cli`
（单一共享身份），导致：①不同员工无法用各自飞书身份导出；②`config.yaml` 写死的
`parent_folder_token` 指向当前 CLI 身份无权写入的文件夹时直接失败。

公司员工均使用飞书。目标：**把飞书 OAuth 直接做成平台登录（飞书 SSO）**，用户点一次
「用飞书登录」授权，平台同时获得：
- 用户身份（用于登录平台、强制门禁）；
- 带云空间权限的 `user_access_token` + `refresh_token`（用于以本人身份导出）。

token 缓存 + 自动刷新：在 `refresh_token` 过期前都**无需重新授权**。

## 2. 选型

- **方案 A（采纳）**：服务端会话（DB 持久化）+ 飞书 OAuth2 授权码流程。token 存后端、
  浏览器只持 httpOnly 会话 cookie。安全、可吊销、与现有 FastAPI + SQLAlchemy 栈一致。
- 方案 B（否决）：JWT 无状态——token/敏感信息暴露给前端 JS，XSS 风险高、难吊销。
- 方案 C（否决）：让每人各自 `lark-cli auth login`——非网页、不符合「点击授权」诉求。

## 3. 飞书接口（已核实，2026-06）

- 授权页：`https://accounts.feishu.cn/open-apis/authen/v1/authorize`
  - query：`client_id`(app_id)、`redirect_uri`、`scope`、`state`
- 换/刷新 token：`POST https://open.feishu.cn/open-apis/authen/v2/oauth/token`
  - 授权码：`grant_type=authorization_code` + `client_id` + `client_secret` + `code` + `redirect_uri`
  - 刷新：`grant_type=refresh_token` + `client_id` + `client_secret` + `refresh_token`
  - 返回 `access_token` / `expires_in` / `refresh_token` / `refresh_token_expires_in` / `scope`
  - **拿 `refresh_token` 必须开通 `offline_access` 权限**（不要硬编码有效期，用返回值）
- 用户信息：`GET https://open.feishu.cn/open-apis/authen/v1/user_info`（Bearer access_token）
- 导出上传（以用户 token）：
  1. `POST /open-apis/drive/v1/files/upload_all`（multipart）→ `file_token`
  2. `POST /open-apis/drive/v1/import_tasks`（`file_extension=xlsx`、`file_token`、`type=sheet`、
     `file_name`、`point.mount_type=1`、`mount_key=<folder_token 或空=根目录>`）→ `ticket`
  3. 轮询 `GET /open-apis/drive/v1/import_tasks/{ticket}` → `job_status`、结果 `token`、`url`
  - 权限：`drive:drive`（覆盖上传+导入）

## 4. 架构与组件

- `server/feishu_oauth.py`：纯函数封装（`build_authorize_url` / `exchange_code` /
  `refresh_token` / `get_user_info`），无状态、可单测（mock httpx）。
- `server/auth.py`：会话与当前用户依赖 `get_current_user`；`ensure_fresh_token`（临过期
  用 refresh 续期，refresh 过期才要求重登）；`AUTH_REQUIRED` 判定（未配密钥则 dev 放行）。
- `server/routers/auth.py`：
  - `GET /api/auth/feishu/login` → 302 跳授权页（生成并暂存 state）
  - `GET /api/auth/feishu/callback?code&state` → 校验 state、换 token、取用户、upsert+建会话、
    下发 cookie、302 回前端
  - `GET /api/auth/me` → 当前登录用户（未登录 401）
  - `POST /api/auth/logout` → 清会话
- `server/feishu_drive.py`：以**当前用户 token** 执行 upload→import→poll；替换导出端点中的
  `lark-cli` 调用。
- 前端：`AuthContext`（拉 `/api/auth/me`）、`RequireAuth` 守卫（强制登录）、`LoginPage`
  （「用飞书登录」按钮）、顶栏用户头像/名字 + 退出。

### 边界（不动）
- `medeval` CLI 评测时往飞书发报告的 `lark_publisher`（走 lark-cli）保持不变。
- 仅改「平台网页导出对话流水」一条链路。
- 导出弹窗的「文件夹 token」输入框保留（选填，留空=个人根目录）。

## 5. 数据模型（新增 2 表）

- `feishu_user`：`open_id`(唯一)、`name`、`avatar_url`、`access_token`、`access_expires_at`、
  `refresh_token`、`refresh_expires_at`、`scope`、`created_at`、`updated_at`。
- `session`：`session_id`(随机, PK)、`open_id`(FK)、`expires_at`、`created_at`。

## 6. 配置与密钥（不进 git）

经 `Settings`（环境变量）：`FEISHU_APP_ID`、`FEISHU_APP_SECRET`、`FEISHU_REDIRECT_URI`
（默认 `http://localhost:5173/api/auth/feishu/callback`）、`SESSION_SECRET`、`FEISHU_SCOPES`
（默认 `offline_access contact:user.base:readonly drive:drive`）。提供 `.env.example`。

> 用户需在飞书开发者后台：①把 redirect URI 加进「重定向 URL」；②开通 scope：
> `offline_access`、`contact:user.base:readonly`、`drive:drive`。

## 7. 防自锁

平台当前无登录且正在使用。若 `FEISHU_APP_ID` 未配置 → `AUTH_REQUIRED=false`，守卫放行
（开发兜底），不会把使用者锁在外面；配齐密钥后才真正强制登录。

## 8. 错误处理

- OAuth 失败/被拒/state 不符 → 302 回前端登录页带错误提示，不抛 500。
- 刷新失败（refresh 过期）→ 清会话、要求重登。
- 导出时上传/导入失败 → 502 + 明确原因（权限/文件夹/重登）。

## 9. 测试（TDD）

- `feishu_oauth` / `feishu_drive`：mock httpx，断言请求 URL/参数/解析。
- `auth`：token 新鲜判定与刷新分支；未配密钥 dev 放行。
- `/api/auth/*` 端点：login 302、callback 建会话、me 401/200、logout。
- 导出端点：改用当前用户 token；未登录时行为。

## 10. 非目标（YAGNI）

不做：细粒度角色权限、租户隔离、token 加密存储（先标注后续加固项）、多应用多品牌。
