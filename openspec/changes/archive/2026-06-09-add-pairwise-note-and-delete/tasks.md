# Tasks

## 1. 后端：备注列 + CRUD
- [x] 1.1 `PairwiseComparison` 加 `note: str`（默认 ""），增量迁移
- [x] 1.2 `schemas`：`PairwiseCreate` 加 `note`；`PairwiseComparisonOut` 加 `note`；新增 `PairwiseNoteUpdate`
- [x] 1.3 `compare` router：create 存 note
- [x] 1.4 `compare` router：`PATCH /pairwise/{id}` 仅改 note（404 兜底）
- [x] 1.5 `compare` router：`DELETE /pairwise/{id}` 级联删（204 / 404）
- [x] 1.6 单测：create 带 note 往返、PATCH 改 note、DELETE 连带 verdict 清空

## 2. 前端
- [x] 2.1 `api.ts`：PairwiseComparison/PairwiseCreate 加 `note`；新增 updatePairwiseNote / deletePairwise
- [x] 2.2 发起页：加「描述（本次对比目的）」输入框，提交带 note、成功后清空
- [x] 2.3 历史列表：加「描述」列（行内可编辑，保存调 PATCH）
- [x] 2.4 操作列：加「删除」按钮（Popconfirm，删后刷新列表）

## 3. 验证与归档
- [x] 3.1 `pytest` 全绿
- [x] 3.2 前端 `npm run typecheck` 通过
- [x] 3.3 `graphify update .` 刷新图谱
- [x] 3.4 `openspec validate --strict` 通过后 `openspec archive`
