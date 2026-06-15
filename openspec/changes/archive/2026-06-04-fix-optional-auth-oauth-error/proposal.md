# Proposal: 修复 token 续期失败把 OAuth 异常当 500 泄漏

## Why

`ensure_fresh_token` 在 access_token 临过期时调 `fo.refresh_token` 续期。当飞书侧拒绝
refresh_token（如 `code=20064` 失效/吊销）会抛 `FeishuOAuthError`，而该异常**未被处理**：
- `get_current_user_optional`（"可选登录"依赖）只 catch `SessionExpired`，于是 OAuth 异常
  直接向上抛出，把**任意使用该依赖的接口**变成 500。
- 实测表现：飞书会话过期后点看板「编辑判据(YAML)→另存为新 benchmark」，
  `POST /api/benchmarks/{id}/derive-yaml` 报 500（前端提示"另存失败"）；其它读 `created_by`
  的接口同样受影响。

## What Changes

- 在 `ensure_fresh_token` 内把 `fo.refresh_token` 抛出的 `FeishuOAuthError` **统一转换为
  `SessionExpired`**：会话已无法续期即等价于过期，让所有既有调用方按既定路径优雅降级
  （optional 依赖清会话返回 None；需登录端点回 401；导出等 live-token 路径已 catch `SessionExpired`）。
- 行为结果：会话过期后 `derive-yaml` 等接口不再 500，正常完成（`created_by` 记为空＝"未知"，
  用户重新登录飞书后恢复署名）。

## Impact

- Affected specs: 无（修正既有"per-user token 自动刷新"行为，不改对外契约）。
- Affected code: `server/auth.py`（`ensure_fresh_token`）、`tests/server/test_auth.py`（+2 回归测试）。
- 判分内核 `medeval/**` 零改动。
