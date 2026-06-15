## 1. Phase 1 — bootstrap 置信区间（reporting）

- [x] 1.1 新增 `medeval/reporter/stats.py`：`bootstrap_ci(samples: list[bool], n_resamples: int, confidence: float, seed: int|None) -> dict`（仅标准库 `random`/`statistics`，确定性 seed）
- [x] 1.2 `medeval/config.py` 新增 `StatsCfg`（`enabled: bool = True`、`bootstrap_resamples: int = 1000`、`confidence: float = 0.95`、`seed: int = 0`），挂到 `RunCfg.stats`
- [x] 1.3 `medeval/models.py` 的 `RunReport` 增 `pass_rate_ci: dict = Field(default_factory=dict)`
- [x] 1.4 `medeval/reporter/aggregator.py` 的 `build_report` 末尾基于 `release_passed` 计算并填充 `pass_rate_ci`（读 `config_snapshot.run.stats`）
- [x] 1.5 `medeval/reporter/markdown_report.py` 通过率旁呈现置信区间，标注"统计估计"
- [x] 1.6 前端 `frontend/`：`RunDashboardPage` 通过率卡片展示区间 + `TrendsPage` 误差棒（后端 `RunDetailOut`/trends 透传 `pass_rate_ci`，DB 增 `pass_rate_ci` 列 + ingest）
- [x] 1.7 测试：已知分布 CI 边界、空样本、全过/全挂、seed 可复现、关闭时不产出 CI

## 2. Phase 2 — OpenTelemetry tracing（observability，新能力）

- [x] 2.1 新增 `medeval/observability/tracing.py`：默认 no-op；`configure_tracing()` + `span()` 上下文管理器；otel 未安装或未启用时零开销、不抛错
- [x] 2.2 `medeval/config.py` 新增 `ObservabilityCfg`（`otel.enabled: bool = False`、`otel.endpoint: str = ""`、`otel.service_name: str = "medeval"`），挂到 `Config.observability`
- [x] 2.3 `medeval/runner/executor.py` `_run_one` 每轮 adapter 调用包 span（属性：sample_id/turn_index/latency_ms/error）
- [x] 2.4 `medeval/service.py` `evaluate` 各 phase（run/judge_det/judge_llm/judge_sp）包 span；LLM/得分点 judge 调用包 span
- [x] 2.5 `pyproject.toml` 新增 `[project.optional-dependencies] otel`
- [x] 2.6 测试：内存 span exporter 断言 span 数量/属性；未启用时无 span、不导入 otel；未安装 otel 时主链路可跑

## 3. Phase 3 — Ray 分布式执行后端（dialog-runner）

- [x] 3.1 `medeval/config.py` `RunCfg` 新增 `executor: Literal["local","ray"] = "local"`（含 `ray_address`、`ray_num_workers` 可选）
- [x] 3.2 抽象：`medeval/runner/executor.py` `run_cases` 增可选 `executor`/`adapter_type`/`adapter_config`/`ray_*` 形参（local 路径忽略，签名向后兼容），并按 `executor` 分派
- [x] 3.3 新增 `medeval/runner/ray_backend.py`：worker 内用 `build_adapter` 自建 adapter，逐 case 跑 N-runs，driver 汇总为 `list[list[ConversationTrace]]`（dict 往返、结构对齐 local）
- [x] 3.4 `medeval/service.py` 把 adapter 构建信息（type+config）传入 `run_cases`，使 ray 路径可在 worker 重建 adapter
- [x] 3.5 `config.yaml` 增 `run.executor`（值=local）；`pyproject.toml` 新增 `[project.optional-dependencies] ray`
- [x] 3.6 测试：local 路径回归不变；ray 缺失抛清晰错误（不回退）；ray 真实集群 + http 桩验证产物结构与 local 一致（无 ray 环境时 skip）

## 4. 收尾

- [x] 4.1 `pytest`（含 `-m golden`）全绿（412 passed）
- [x] 4.2 `medeval run --config config.yaml --dry-run` 通过（加载 71 条用例、新配置字段校验通过）
- [x] 4.3 `graphify update .` 刷新图谱
- [x] 4.4 `openspec validate --strict` 通过后归档
