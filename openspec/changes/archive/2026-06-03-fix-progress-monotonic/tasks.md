## 1. 测试先行（TDD）

- [x] 1.1 `tests/server/test_jobs.py`：声明 4 阶段计划后，逐阶段推进，`snapshot().percent`
  在阶段切换处不回退（单调非降），首阶段满载时 < 100%，全部满载时 == 100%
- [x] 1.2 `tests/server/test_jobs.py`：未声明计划时 `percent` 仍按当前阶段口径（向后兼容）
- [x] 1.3 `tests/test_service.py`：`evaluate` 开跑前通过观察者声明阶段计划（记录式 observer
  收到 plan，含 run/judge_det，启用项才含 judge_llm/judge_sp）

## 2. 实现

- [x] 2.1 `ProgressObserver` 协议 + `NullProgress` 增加 `plan_phases`
- [x] 2.2 `medeval/cli.py` `RichProgress.plan_phases`（no-op）
- [x] 2.3 `server/progress.py` `InMemoryProgress.plan_phases` + `snapshot` 全局百分比
- [x] 2.4 `medeval/service.py` 开跑前构造并上报阶段计划

## 3. 收尾

- [x] 3.1 全量 `pytest` 绿
- [x] 3.2 `medeval run --config config.yaml --dry-run`
- [x] 3.3 刷新图谱 + `openspec validate --strict` 通过后 `openspec archive`
