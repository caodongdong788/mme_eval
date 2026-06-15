## Why

评测列表的进度条在快到 100% 时会突然回到 0% 重新开始。根因：进度百分比只按**当前阶段**
（`run` / `judge_det` / `judge_llm` / `judge_sp`）的 `done/total` 计算，而一次评测最多有 4 个
顺序阶段，每切到下一阶段就把基数清零——用户看到的「近 100% 回到 0%」正是 `调用 chatbot`
阶段跑完、`判分` 阶段开始的瞬间。这是进度上报口径 bug，不是执行回退。

## What Changes

- `medeval/service.py`：在评测开跑前，根据已知信息（用例数 × repeat、是否启用 LLM/得分点
  judge）一次性**声明完整阶段计划**（各阶段及其 total），通过 `ProgressObserver.plan_phases`
  上报。
- `medeval/service.py` 的 `ProgressObserver` 协议、`NullProgress`、`medeval/cli.py` 的
  `RichProgress` 增加 `plan_phases`（CLI 实现为 no-op，保持原 rich 逐阶段渲染）。
- `server/progress.py` 的 `InMemoryProgress`：记录阶段计划总量，`snapshot().percent` 改为
  **全局累计百分比**（已声明计划时 = Σ各阶段 done / Σ各阶段 total），保证单调不回退；未声明
  计划时回退原「当前阶段」口径（向后兼容）。`current_label` / `done` / `total` 仍取当前阶段
  供 tooltip 展示。

## Capabilities

### Modified Capabilities
- `eval-platform-service`: 运行进度的百分比口径明确为「跨阶段全局单调」，不得回退。

## Impact

- 修改：`medeval/service.py`、`medeval/cli.py`、`server/progress.py`。
- 测试：`tests/server/test_jobs.py`（plan_phases 后跨阶段单调不回退）、
  `tests/test_service.py`（evaluate 上报阶段计划）。
