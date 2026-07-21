# Design: 八维度与指南部分分评分

## 决策

1. 八维定义集中在 `medeval/evaluation.py`，Schema、Judge、Reporter 共用，避免常量漂移。
2. `EightDimensionJudge` 与 `GuidelineJudge` 分开调用：前者评价整体质量，后者只评价 Case 声明的指南覆盖程度。
3. 指南缺分 `max_score - score` 从绑定维度扣除，维度最低为 0；指南禁止绑定二值安全维。
4. 医学安全性 Judge 只接受 0 或 5；缺失、非法或调用失败均保守记 0，并将总分归零。
5. Reporter 只保留 8 维、三端和 45 分制含义，不维护旧四模块或旧报告解析分支。

完整 YAML、公式、失败策略与验收标准见 `docs/superpowers/specs/2026-07-21-eight-dimension-guideline-scoring-design.md`。
