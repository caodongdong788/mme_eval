# Tasks

## 1. TDD（先写/改测试）
- [x] 1.1 改 `_stub` 用例返回 `1/2/tie`（位置标签），更新所有现有断言
- [x] 1.2 prompt 双盲断言：含「系统①」「系统②」、不含「基线」「本次」「甲」「乙」、不泄露身份
- [x] 1.3 映射断言：pass①判 1、pass②判 1（位置一致但身份相反）→ swap_consistent=false、tie、low
- [x] 1.4 映射断言：两次都判"上面的内容对应同一真实系统"更优 → winner=该身份、high
- [x] 1.5 reason 翻译断言：含「系统①」的 reason 落库为 A/B 文本
- [x] 1.6 order_runs 断言：两条、各含 top/winner(已映射)/reason(已翻译)
- [x] 1.7 医疗保守 / confidence 分档 / fingerprint 既有用例适配

## 2. 实现 medeval/pairwise.py
- [x] 2.1 `_PROMPT_TEMPLATE` 改中性占位 + 证据优先引导 + 输出契约 1/2/tie
- [x] 2.2 `_conversation_blocks` 改匿名「系统①/系统②」并接收 (top_trace, bottom_trace)
- [x] 2.3 新增 `_resolve_side(value, top_is, bottom_is)` 与 `_relabel(text, top_is, bottom_is)`
- [x] 2.4 `compare_case` 双盲两次映射 + `_resolve`/翻译 + `order_runs` 组装
- [x] 2.5 `PairwiseResult` 加 `order_runs: list[dict]`

## 3. 后端落库
- [x] 3.1 `PairwiseCaseVerdict` 加 `order_runs` JSON 列（增量迁移）
- [x] 3.2 `schemas.PairwiseCaseVerdictOut` 加 `order_runs`
- [x] 3.3 `pairwise_job.run_pairwise_comparison` 落 `order_runs`

## 4. 前端
- [x] 4.1 `api.ts`：PairwiseCaseVerdict 加 `order_runs`
- [x] 4.2 详情页：顺序敏感用例如实并列两次分歧（一致仍单条 reason）

## 5. 验证与归档
- [x] 5.1 `pytest` 全绿（pairwise 单测 + server 后端）
- [x] 5.2 前端 `npm run typecheck` 通过
- [x] 5.3 `medeval run --config config.yaml --dry-run`（评测端零变化自检）
- [x] 5.4 `graphify update .` 刷新图谱
- [x] 5.5 `openspec validate --strict` 通过后 `openspec archive`
