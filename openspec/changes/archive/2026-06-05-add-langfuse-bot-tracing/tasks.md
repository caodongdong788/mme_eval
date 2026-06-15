# Tasks

- [x] 1. graphify update . 刷新图谱（启动）
- [x] 2. TDD：新增 `tests/test_langfuse_tracing.py`（关闭 no-op / 启用时 generation 的 input/output/usage / root+会话嵌套 / on-off 判分一致的零侵入不变量 / 软依赖不报错）
- [x] 3. `pyproject.toml` 新增 `langfuse` 可选 extra
- [x] 4. `medeval/config.py` 新增 `LangfuseCfg` 挂到 `ObservabilityCfg.langfuse`；`config.yaml` 补默认关闭段
- [x] 5. 新增 `medeval/observability/langfuse_tracing.py`（configure_langfuse / conversation / generation / update_generation / flush / shutdown，软依赖 + no-op 兜底 + 异常静默）
- [x] 6. `medeval/runner/executor.py`：`_run_one` 透传 `run_idx`，turn 循环外包会话 span，`adapter.chat` 处建并回填 generation
- [x] 7. `medeval/service.py`：`evaluate` 调 `configure_langfuse` 并 finally flush；`run_traces` 的 `phase.run` 处开仅覆盖 bot 阶段的 root trace
- [x] 8. 验证：全量 pytest 绿 + graphify update . + `medeval run --config config.yaml --dry-run` + `openspec validate --strict` 后归档
