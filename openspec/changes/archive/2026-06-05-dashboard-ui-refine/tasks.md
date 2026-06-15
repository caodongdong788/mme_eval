# Tasks

- [ ] 1. TDD：`tests/server/test_runs_rename.py`（改名成功 / 空名 422 / 重名 409 / 未知 404 / 同名自身允许）
- [ ] 2. 后端：`schemas.RunRenameRequest` + `PATCH /api/runs/{run_id}` 改名端点（重名校验，排除自身）
- [ ] 3. 前端 `api.ts`：`renameRun(id, name)`
- [ ] 4. 前端看板：移除「人工审核」tab
- [ ] 5. 前端看板：失败标签分布改饼图
- [ ] 6. 前端看板：分层级通过率改「数量 + 通过率」组合图并优化样式
- [ ] 7. 前端看板：标题双击改名（自动保存 + 重名提示）
- [ ] 8. 前端看板：meta 精简为 judge 模型 + N
- [ ] 9. 验证：pytest（server）+ tsc + vite build + 浏览器走查 + graphify update + openspec validate/archive
