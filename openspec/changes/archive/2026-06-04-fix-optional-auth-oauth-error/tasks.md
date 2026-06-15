# Tasks

## 1. 排障 + 回归测试（TDD）
- [x] 1.1 定位：`POST /derive-yaml` 500 源于 `get_current_user_optional` 漏 catch `FeishuOAuthError`
- [x] 1.2 写测试：`ensure_fresh_token` 把 `FeishuOAuthError` 转 `SessionExpired`
- [x] 1.3 写测试：`get_current_user_optional` 刷新失败时清会话并返回 None（不抛错）

## 2. 修复
- [x] 2.1 `ensure_fresh_token` try/except 包裹 `fo.refresh_token`，转 `SessionExpired`

## 3. 验证
- [x] 3.1 `pytest tests/server/test_auth.py` 绿
- [x] 3.2 全量 `pytest` 绿（458 passed）
- [x] 3.3 `graphify update .` + `openspec validate --strict` + archive
