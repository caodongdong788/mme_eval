# Tasks

## 1. 测试先行（TDD）
- [x] 1.1 `tests/test_diff_latency.py`：`_latency_diff` 两版都有数据 → 含「性能变化」表、当前/上版/Δ、方向标注、数值正确
- [x] 1.2 上版本缺 `latency_summary` → 返回 ℹ️ 提示且不抛错
- [x] 1.3 当前缺 `latency_summary` → 返回空串（不输出该块）
- [x] 1.4 `diff_runs` 集成：两份 json 都有延迟时，输出末尾含「性能变化」块

## 2. 实现
- [x] 2.1 `medeval/reporter/diff.py` 新增 `_latency_diff(cur, prev) -> str`
- [x] 2.2 `diff_runs` 在既有内容末尾接入性能对比块

## 3. 验证
- [x] 3.1 全量 `pytest` 绿（327 passed）
- [x] 3.2 真实 config `medeval run --config config.yaml --dry-run` 通过
- [x] 3.3 `graphify update .` 刷新图谱
- [x] 3.4 `openspec validate --strict` 通过并归档
