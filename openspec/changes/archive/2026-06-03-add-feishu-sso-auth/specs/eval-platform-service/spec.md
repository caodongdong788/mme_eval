## ADDED Requirements

### Requirement: 对话流水导出以登录用户身份上传飞书

系统 SHALL 在导出对话流水（`POST /api/runs/{run_id}/export-transcripts`）时，使用**当前
登录用户的 `user_access_token`** 直接调用飞书 OpenAPI（`drive/v1/files/upload_all` →
`drive/v1/import_tasks` → 轮询 `import_tasks/{ticket}`）将 xlsx 导入为在线表格，不再依赖
`lark-cli` 的共享身份。目标文件夹 `mount_key` 取调用方传入的 token，空值 MUST 表示个人
空间根目录。上传或导入失败时系统 MUST 返回 502 及可操作的失败原因（权限/文件夹/重登）。

#### Scenario: 登录用户导出成功

- **WHEN** 已登录用户按过滤条件请求导出对话流水
- **THEN** 系统以该用户飞书 token 上传并导入为在线表格，返回飞书表格 URL、用例数与文件名

#### Scenario: 传入文件夹 token

- **WHEN** 用户在导出时传入飞书文件夹 token
- **THEN** 系统将表格导入到该文件夹（需该用户对其有写权限）；传空则导入到个人根目录

#### Scenario: 导入失败返回可操作原因

- **WHEN** 上传或导入任务失败（无权限/文件夹不可写/token 失效）
- **THEN** 系统返回 502 并给出明确原因与下一步建议
