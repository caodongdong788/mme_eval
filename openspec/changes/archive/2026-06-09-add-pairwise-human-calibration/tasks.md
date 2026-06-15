# Tasks

## 1. 后端有效值 + 汇总
- [x] 1.1 PairwiseCaseVerdict 加 human_* 列
- [x] 1.2 `verdict_effective_row` + 扩展 `_summarize` + `recompute_pairwise_summary`
- [x] 1.3 schemas：PairwiseCaseVerdictOut（confidence_kind + auto_*）+ PairwiseCalibrateUpdate
- [x] 1.4 router：PATCH 校准 / DELETE 恢复 + 重算 summary
- [x] 1.5 单测：校准后 summary 联动、恢复机器判定

## 2. 前端
- [x] 2.1 api.ts 类型 + calibratePairwiseVerdict / resetPairwiseVerdict
- [x] 2.2 PairwiseCalibrateModal 组件
- [x] 2.3 PairwiseDetailPage：筛选 A/B/持平 + 置信含人工校准；统计读 summary；行内校准

## 3. 验证归档
- [x] 3.1 pytest 全绿 + typecheck
- [x] 3.2 graphify + openspec archive
