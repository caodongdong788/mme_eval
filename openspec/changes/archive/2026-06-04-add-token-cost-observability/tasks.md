## 1. 模型字段（schema）

- [x] 1.1 `ConversationTrace` 增 `turn_token_usage: list[dict] = Field(default_factory=list)`（逐轮 prompt/completion/total）
- [x] 1.2 `CaseResult` 增 `per_run_tokens: list[int] = Field(default_factory=list)`
- [x] 1.3 `RunReport` 增 `token_summary: dict = Field(default_factory=dict)`

## 2. 配置（cost 单价）

- [x] 2.1 `medeval/config.py` 增 `CostConfig`（currency / input_per_million / output_per_million，默认全 0 = 未配置）
- [x] 2.2 `config.yaml` 新增 `cost:` 段（含注释说明"仅观测、单价随 snapshot 落盘"）
- [x] 2.3 确认 `cost` 进入 `config_snapshot` 供 diff 解释

## 3. Runner 采集

- [x] 3.1 `runner/executor.py` 加 `_extract_token_usage(raw) -> dict` 归一化器（认 OpenAI 三键，认不出返回 `{}`）
- [x] 3.2 在 `turn_latencies_ms.append(...)` 同处、裁剪之前 append `turn_token_usage`
- [x] 3.3 `runner/voting.py` 在 `per_run_latency_ms` 赋值旁，从 `turn_token_usage` 求和折叠 `per_run_tokens`（N=1 与 N>1 两分支）

## 4. 聚合与报告

- [x] 4.1 `reporter/aggregator.py` 加 `_token_summary(results, pricing)`，过滤 `trace.error` 非空 run，产出 token 统计（无数据→ `{}`）
- [x] 4.2 配置非零单价时折算 cost（input/output 分别计价）并写入 token_summary；单价全 0 则不出 cost
- [x] 4.3 `build_report` 从 `config_snapshot["cost"]` 取 pricing 传入 `_token_summary`
- [x] 4.4 `reporter/markdown_report.py` 加 `_token_section()`，标注"仅观测、不计分、不否决（仅被测 bot）"，无数据显示 N/A
- [x] 4.5 `reporter/diff.py` 加 `_token_diff()`，当前/上版/Δ，历史报告缺字段时友好降级

## 5. 平台（server + frontend）

- [x] 5.1 `server/models_db.py`：`RunRow` 加 `token_summary`，`CaseRow` 加 `total_tokens` / `cost`
- [x] 5.2 `server/schemas.py`：对应 Pydantic 字段（默认空）
- [x] 5.3 `server/ingest.py`：落库 `report.token_summary` 与 case 级 token/cost（`sum(cr.per_run_tokens)`）
- [x] 5.4 `frontend/src/api.ts`：`RunReport` 接口加 `token_summary`
- [x] 5.5 `frontend/src/pages/RunDashboardPage.tsx`：新增"成本 / Token（仅观测）"Card

## 6. 测试（TDD，先写后实现）

- [x] 6.1 单测：`_extract_token_usage` 认 openai usage、认不出返回 `{}`、不抛错
- [x] 6.2 单测：成功轮次采集 token；`store_raw=on_error` 裁剪后 `turn_token_usage` 仍在
- [x] 6.3 单测：token 字段不影响 `gate_passed` / `release_passed` / 各 verdict
- [x] 6.4 单测：N=3 时 `per_run_tokens` 长度为 3；`token_summary` 含总 token / 平均
- [x] 6.5 单测：错误 run 不计入 token 聚合
- [x] 6.6 单测：配置单价→出 cost；未配置→cost N/A
- [x] 6.7 单测：diff 在历史报告缺 `token_summary` 时友好降级不抛错
- [x] 6.8 单测（server）：ingest 落库 token_summary 与 case 级 token/cost；历史 run 缺字段安全读取
- [x] 6.9 单测：历史无 token 字段的 report.json 仍可反序列化（默认值兼容）

## 7. 收尾验证

- [x] 7.1 全量 `pytest` 绿
- [x] 7.2 `graphify update .` 刷新图谱
- [x] 7.3 `medeval run --config config.yaml --dry-run` 跑通
- [x] 7.4 `openspec validate --strict` 通过
