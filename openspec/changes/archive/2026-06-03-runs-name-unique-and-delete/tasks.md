## 1. 后端（TDD）

- [x] 1.1 先写 `tests/server/test_api.py`：重名发起返回 409；删除已完成 run → 204 且后续 404；删除不存在 → 404；删除 running/pending → 400
- [x] 1.2 `create_run` 增加最终名称唯一性校验（重名 409）
- [x] 1.3 新增 `DELETE /api/runs/{run_id}`：级联删除 + 清理 outputs 目录 + 运行中拒绝

## 2. 前端

- [x] 2.1 `api.ts` 增 `deleteRun`
- [x] 2.2 `RunsPage` 列宽改为内容自适应；操作栏加「删除」（Popconfirm 二次确认 + 重载）

## 3. 收尾

- [x] 3.1 全量 `pytest` 绿
- [x] 3.2 前端 `tsc` 零报错
- [x] 3.3 刷新图谱 + `openspec validate --strict` 通过后 `openspec archive`
