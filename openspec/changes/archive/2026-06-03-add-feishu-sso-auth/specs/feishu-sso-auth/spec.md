## ADDED Requirements

### Requirement: 飞书 OAuth2 授权码登录

系统 SHALL 提供基于飞书 OAuth2 授权码流程的登录入口：`GET /api/auth/feishu/login` 生成
带 `client_id`、`redirect_uri`、`scope`、随机 `state` 的飞书授权页 URL 并 302 跳转；
`GET /api/auth/feishu/callback` MUST 校验 `state`、用 `code` 调
`authen/v2/oauth/token` 换取 `user_access_token` 与 `refresh_token`、调 `user_info` 取身份。
授权请求的 scope MUST 包含 `offline_access` 以获得 `refresh_token`。

#### Scenario: 发起登录跳转飞书授权页

- **WHEN** 未登录用户访问 `GET /api/auth/feishu/login`
- **THEN** 系统生成随机 state 并 302 跳转到飞书授权页，URL 含 client_id/redirect_uri/scope/state

#### Scenario: 回调换 token 并建立会话

- **WHEN** 飞书回调 `GET /api/auth/feishu/callback?code&state` 且 state 校验通过
- **THEN** 系统换取 token、取用户信息、upsert `feishu_user`、创建 `session` 并下发 httpOnly cookie，再 302 回前端首页

#### Scenario: state 不匹配拒绝

- **WHEN** 回调携带的 state 与服务端暂存值不一致
- **THEN** 系统 MUST NOT 建立会话，且 302 回前端登录页并带错误提示

### Requirement: 服务端会话与当前用户

系统 SHALL 用服务端会话（`session` 表 + httpOnly cookie）维护登录态；MUST 提供
`get_current_user` 依赖解析当前用户；`GET /api/auth/me` 返回当前用户、未登录返回 401；
`POST /api/auth/logout` MUST 清除会话。cookie 仅存随机 `session_id`，token 不下发到浏览器。

#### Scenario: 查询当前登录用户

- **WHEN** 已登录用户请求 `GET /api/auth/me`
- **THEN** 系统返回该用户 open_id、name、avatar

#### Scenario: 未登录访问 me

- **WHEN** 无有效会话 cookie 的请求访问 `GET /api/auth/me`
- **THEN** 系统返回 401

#### Scenario: 退出登录

- **WHEN** 已登录用户请求 `POST /api/auth/logout`
- **THEN** 系统删除其会话记录，后续请求视为未登录

### Requirement: per-user token 缓存与自动刷新

系统 SHALL 持久化每个飞书用户的 `user_access_token`、`refresh_token` 及各自有效期；当访问
受保护接口时若 `access_token` 已过期或临近过期，系统 MUST 用 `refresh_token` 自动续期并
回写数据库，避免重复授权；当 `refresh_token` 也已过期时，系统 MUST 清除会话并要求重新登录。
有效期 MUST 取飞书返回的 `expires_in` / `refresh_token_expires_in`，不得硬编码。

#### Scenario: access 临过期自动刷新

- **WHEN** 受保护接口被访问且当前用户 access_token 临近过期但 refresh_token 仍有效
- **THEN** 系统用 refresh_token 换新 token、回写数据库，请求照常完成，用户无感

#### Scenario: refresh 过期要求重登

- **WHEN** 用户 refresh_token 也已过期
- **THEN** 系统清除会话并返回 401，前端引导重新授权

### Requirement: 强制登录门禁与开发兜底

系统 SHALL 在配置了飞书应用密钥（`FEISHU_APP_ID`）时对业务接口与前端页面强制登录；
当未配置 `FEISHU_APP_ID` 时 `AUTH_REQUIRED` MUST 为 false，守卫放行以避免本地开发自锁。

#### Scenario: 配齐密钥时强制登录

- **WHEN** 配置了 FEISHU_APP_ID 且未登录请求访问受保护业务接口
- **THEN** 系统返回 401（或前端跳转授权页）

#### Scenario: 未配密钥时放行

- **WHEN** 未配置 FEISHU_APP_ID
- **THEN** 守卫放行，平台可匿名访问，不阻断本地开发
