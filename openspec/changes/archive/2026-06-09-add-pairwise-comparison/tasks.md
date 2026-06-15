# Tasks: add-pairwise-comparison

## 1. 判分内核：PairwiseComparator（TDD）

- [x] 1.1 写测试 `tests/test_pairwise_comparator.py`（mock LLMBackend）：
  - B 明显更优 → winner=B、dimension_winners.safety=B、reason 非空
  - 两份无差距 → tie
  - 位置消偏：两次不一致 → tie + confidence=low + swap_consistent=false
  - 位置消偏：两次一致 → winner=该方 + confidence=high
  - 医疗保守：某顺序 safety 判某方差 → 整体不得为该方
  - fingerprint：改 prompt 模板后值变化；排除 api_key/base_url
- [x] 1.2 实现 `medeval/pairwise.py::PairwiseComparator`：
  - `__init__`（provider/model/temperature/swap_debias 等，构造 LLMBackend）
  - `compare_case(case, trace_a, trace_b)`：两次交换调用 + 聚合 + 保守覆盖
  - prompt 模板（仅输出 JSON：winner/dimension_winners/reason）+ `_parse`
  - `fingerprint()`
- [x] 1.3 `pytest tests/test_pairwise_comparator.py` 全绿

## 2. 平台后端：发起/校验/落库/查询

- [x] 2.1 `server/models_db.py` 新增 `PairwiseComparison` / `PairwiseCaseVerdict`
- [x] 2.2 `server/db.py` 启动幂等建表（IF NOT EXISTS 同款迁移）
- [x] 2.3 可比性校验函数（扩 `server/compare.py` 或新模块）：benchmark/sample_id 集合/
  judge_fingerprints/scoring/has_traces；并产出 `subject_diff`
- [x] 2.4 `server/schemas.py` 新增 pairwise 入参/出参 schema
- [x] 2.5 路由：`POST /api/compare/pairwise`（校验→建 running→异步逐题）、
  `GET /api/compare/pairwise/{id}`（总结+列表，自库读）
- [x] 2.6 异步执行 + 启动回收孤儿（复用 `server/jobs.py` 模式）
- [x] 2.7 后端测试：可比性校验各拒绝分支 + 发起→落库→查询冒烟（mock comparator）

## 3. 前端：入口 + 列表 + 详情 + 总结

- [x] 3.1 `frontend/src/api.ts` 接入两个新接口的类型与调用
- [x] 3.2 「Pairwise 对比」入口：选两 run + 裁判模型，不可比时中文报错
- [x] 3.3 结果页：①整体总结（胜/平/负 + 维度胜率 + 回退清单 + subject_diff）
  ②逐用例列表（按 winner 筛选/排序）③单题详情 A/B 左右并排 + 理由
- [x] 3.4 样式遵循 DESIGN.md（teal 胜/灰平/警示负；数字 mono）；token 单一信任源

## 4. 收尾与验证

- [x] 4.1 `pytest` 全量绿
- [x] 4.2 `medeval run --config config.yaml --dry-run` 通过（确认内核新增不破坏主链路）
- [x] 4.3 `graphify update .` 刷新图谱
- [x] 4.4 `openspec validate add-pairwise-comparison --strict` 通过
- [x] 4.5 `openspec archive add-pairwise-comparison` 并同步规格
