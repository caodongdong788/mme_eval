# eval-platform-service Specification (delta)

## ADDED Requirements

### Requirement: 登录会话 token 续期失败时优雅降级

系统 MUST 把飞书拒绝 `refresh_token` 的续期失败（如 `code=20064` 失效/吊销）视为会话过期处理，MUST NOT 将底层 OAuth 异常作为未处理错误向上抛出。具体而言：

- "可选登录"依赖（用于读取 `created_by` 等署名信息的接口）在续期失败时 MUST 清理该会话并
  返回未登录（None），使接口仍能完成（署名记为空）；
- 任意使用该可选依赖的接口（如 `POST /api/benchmarks/{id}/derive-yaml`、benchmark 上传/派生）
  MUST NOT 因会话过期而返回 500。

#### Scenario: 会话过期不再 500

- **WHEN** 用户飞书会话已过期（refresh 被拒），调用一个用"可选登录"获取署名的接口
- **THEN** 系统 MUST 清理过期会话、以未登录身份完成请求，MUST NOT 返回 500
