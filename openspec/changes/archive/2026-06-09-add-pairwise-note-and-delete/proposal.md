# Proposal: Pairwise 对比备注 + 删除

## Why

Pairwise 历史列表里多条对比仅以「#A vs #B + 裁判」区分，跑多了无法回忆「这次对比是为验证什么」。
同时失败/误发起的对比记录无法清理，只能堆积。需要：
- 发起时填一句**对比目的备注**，列表可见、可二次编辑；
- 历史列表可**删除**某次对比（连带其逐用例结论）。

## What Changes

- `PairwiseComparison` 新增 `note: str`（备注/目的，默认 ""），走既有增量迁移。
- 发起接口 `POST /api/compare/pairwise` 接受 `note`；新增
  `PATCH /api/compare/pairwise/{id}`（仅改 `note`，二次编辑）与
  `DELETE /api/compare/pairwise/{id}`（级联删逐用例 verdict）。
- 前端发起页加「描述（本次对比目的）」输入框；历史列表加「描述」列（行内可编辑）；
  操作列加「删除」按钮（Popconfirm 确认）。

## Impact

- Affected specs: `eval-platform-service`（Pairwise 对比备注与删除）
- Affected code:
  - `server/models_db.py`（PairwiseComparison 加 `note` 列）
  - `server/schemas.py`（PairwiseCreate/Out + 新增 PairwiseNoteUpdate）
  - `server/routers/compare.py`（create 存 note + PATCH + DELETE 端点）
  - `frontend/src/api.ts`、`frontend/src/pages/PairwisePage.tsx`
- 兼容性：`note` 带默认 ""，旧记录自动获空备注；不改判分语义、不影响 `summary`/可比性校验。
- 删除依赖既有 `verdicts` 关系 `cascade="all, delete-orphan"`，物理删除一次对比及其全部 verdict。
