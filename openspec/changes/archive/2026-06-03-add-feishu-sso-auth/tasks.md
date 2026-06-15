## 1. 配置与密钥

- [x] 1.1 `server/settings.py` 增 `feishu_app_id` / `feishu_app_secret` / `feishu_redirect_uri` / `feishu_scopes` / `session_secret` / `auth_required`（由 app_id 是否配置推导）
- [x] 1.2 新增 `.env.example` 列出飞书 OAuth 与会话相关环境变量
- [x] 1.3 写 settings 测试：未配 app_id 时 `auth_required=False`，配了则 True

## 2. 数据模型

- [x] 2.1 `server/models_db.py` 增 `FeishuUser`（open_id 唯一、name、avatar_url、access_token、access_expires_at、refresh_token、refresh_expires_at、scope、时间戳）
- [x] 2.2 `server/models_db.py` 增 `Session`（session_id PK、open_id、expires_at、created_at）
- [x] 2.3 写建表测试：`init_db` 后两表存在、字段/约束正确

## 3. 飞书 OAuth 纯函数封装（TDD）

- [x] 3.1 先写 `tests/server/test_feishu_oauth.py`：mock httpx 断言 `build_authorize_url` 含 client_id/redirect_uri/scope/state；`exchange_code`/`refresh` 请求体与解析；`get_user_info` 请求头与解析
- [x] 3.2 实现 `server/feishu_oauth.py` 使测试通过

## 4. 会话与当前用户（TDD）

- [x] 4.1 先写 `tests/server/test_auth.py`：会话创建/查询/过期；`ensure_fresh_token` 临过期触发刷新并回写、refresh 过期返回需重登；`auth_required` 推导
- [x] 4.2 实现 `server/auth.py`：`create_session`/`resolve_session`/`get_current_user` 依赖/`ensure_fresh_token`

## 5. 认证路由（接口测试）

- [x] 5.1 先写 `tests/server/test_auth_api.py`：`/api/auth/feishu/login` 302 含授权 URL；`callback` mock oauth 后建会话+set-cookie+302；state 不符回登录页；`/api/auth/me` 401/200；`logout` 清会话
- [x] 5.2 实现 `server/routers/auth.py` 并在 `server/app.py` 挂载

## 6. 飞书云空间导入（TDD）

- [x] 6.1 先写 `tests/server/test_feishu_drive.py`：mock httpx 断言 `upload_all` multipart、`import_tasks` 请求体（file_extension/type/mount_key 空=根目录）、轮询 ticket 直到完成并解析 url；失败路径
- [x] 6.2 实现 `server/feishu_drive.py`：`import_xlsx_as_sheet(token, xlsx_path, folder_token, title)`

## 7. 导出端点改造（测试）

- [x] 7.1 改 `server/routers/runs.py` 导出端点：取当前登录用户 → `ensure_fresh_token` → 调 `feishu_drive`；保留 `parent_folder_token` 入参语义（空=根目录）
- [x] 7.2 更新 `tests/server/test_api.py::test_export_transcripts`：mock 当前用户与 `feishu_drive`，断言用用户 token 上传、传入文件夹 token 透传、未登录行为

## 8. 强制登录守卫（测试）

- [x] 8.1 在 `server/app.py` 接入守卫：`auth_required=True` 时业务接口未登录返回 401；`/api/auth/*`、`/api/health` 豁免
- [x] 8.2 写测试：配密钥时受保护接口 401、豁免接口可访问；未配密钥时全部放行

## 9. 前端

- [x] 9.1 `frontend/src/api.ts` 增 `getMe` / `logout` / login 跳转，axios `withCredentials: true`
- [x] 9.2 新增 `AuthContext` + `RequireAuth` 守卫；401 时跳转 `/login`
- [x] 9.3 新增 `LoginPage`（「用飞书登录」按钮，跳 `/api/auth/feishu/login`，展示回调错误）
- [x] 9.4 顶栏展示用户头像/名字 + 退出；接入路由守卫
- [x] 9.5 `npx tsc --noEmit` 通过

## 10. 收尾与归档

- [x] 10.1 全量 `pytest` 绿
- [x] 10.2 前端 `tsc` 零报错
- [x] 10.3 `medeval run --config config.yaml --dry-run` 跑通
- [x] 10.4 `graphify update .` 刷新图谱
- [x] 10.5 `openspec validate add-feishu-sso-auth --strict` 通过后 `openspec archive`
