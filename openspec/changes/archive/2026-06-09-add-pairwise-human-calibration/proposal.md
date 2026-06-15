# Proposal: Pairwise 人工校准 + 报告统计联动

## Why

Pairwise 对比存在大量顺序敏感/安全存疑的自动判定，需专家人工覆写结论后才能作为发布依据。
现有逐用例结果只读，无法改结论/维度/理由；报告汇总在对比完成后写死，不随人工修正更新。

## What Changes

- **人工校准**：逐用例可覆写 `winner`（A更好/B更好/持平）、三维度归属、`reason`；保存后
  `confidence_kind=human`（人工校准）。保留机器原判字段供对照，可随时「恢复机器判定」。
- **统计联动**：校准/恢复后 MUST 按**有效值**（有人工则用人工，否则用机器）重算
  `PairwiseComparison.summary`（胜/平/负、低置信细分、维度胜率、overall_winner、回退/改善清单）。
- **API**：`PATCH /api/compare/pairwise/{id}/cases/{sample_id}` 提交校准；
  `DELETE` 同路径恢复机器判定。详情/列表回显有效值 + `confidence_kind`。
- **前端**：结论筛选改为 A更好/B更好/持平；置信筛选含「人工校准」；表格行内「校准」入口 +
  表单 Modal；概览统计读重算后的 `summary` 与 `confidence_kind` 细分。

## Impact

- Affected specs: `eval-platform-service`, `judging-pipeline`（Pairwise 有效值与汇总口径）
- Affected code: `server/models_db.py`, `server/pairwise_job.py`, `server/routers/compare.py`,
  `server/schemas.py`, `frontend/src/api.ts`, `frontend/src/pages/PairwiseDetailPage.tsx`,
  新建 `frontend/src/components/PairwiseCalibrateModal.tsx`
- 不进 gate；机器原判字段保留，summary 以有效值为准（与 run HITL 旁路不同，此处故意写回汇总）。
