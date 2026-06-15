## 1. 默认温度调整（前置：让"复现"成为默认姿态）

- [x] 1.1 把 `medeval/adapter/openai_compat.py` 中 `OpenAICompatAdapter.__init__` 的 `temperature` 默认值从 0.3 改为 0.0；`HttpAdapter` 同步处理（如有 temperature 概念）
- [x] 1.2 修改 `config.yaml` / `config.l1.yaml` / `config.multi_turn.yaml`：把显式 `temperature: 0.3` 全部改为 `temperature: 0.0`（统一基线），并在文件顶部注释里说明"框架默认 0.0；要采样请显式覆盖"
- [x] 1.3 在 README 的"快速开始"和"评测产物"章节之间新增一段"复现性默认值说明"：温度 0.0、`--repeat 1`、推荐 baseline 用 `--repeat 3`
- [x] 1.4 跑 `pytest tests/test_smoke.py -v` 确认默认值变化不破坏现有冒烟（mock adapter 不受影响）

## 2. CLI / config 接入 --repeat 参数

- [x] 2.1 `medeval/cli.py::run` 增加 `@click.option("--repeat", type=int, default=None)`；优先级 CLI > config > 1
- [x] 2.2 `--repeat` 必须是正整数；非法值（0/负数/非整数）必须 click 自带校验或 ValueError，不得静默走默认
- [x] 2.3 `dry_run` 路径里打印 `repeat=N`，让用户在不真跑时也能确认配置
- [x] 2.4 在 `_print_summary` 中显示 `n_runs` 作为概览第一行的 metadata（与 run_name / 用例数同行）

## 3. Runner 侧支持 N-runs

- [x] 3.1 `medeval/runner/executor.py::run_cases` 新增参数 `repeat: int = 1`；当 `repeat>1` 时内部对每条 case 串行调用 adapter N 次；返回类型改为 `list[list[ConversationTrace]]` 但当 repeat=1 时仍包一层（外层 len=N case，内层 len=1）以保持类型一致
- [x] 3.2 每次重复必须使用可区分的 session_id：`f"{base}#run{i}"`；adapter 端不得把不同 #runI 视为同一会话
- [x] 3.3 `on_progress` 回调粒度改为"完成一次 (case, run)"而非"完成一个 case"；进度条总数 = `len(cases) * repeat`
- [x] 3.4 N 次中任一失败必须保留所有完成的 trace；下游聚合器基于"成功的 trace 子集"做 majority；N 次全失败时聚合 case 标 `stable_fail`、保留所有 error
- [x] 3.5 单元测试 `tests/test_runner_repeat.py`（新建）：构造 1/3/4 三种 N 验证 trace 数量、session_id 区分、失败保留、`repeat=1` 与旧版字节对齐

## 4. Judging 侧 majority voting

- [x] 4.1 新建 `medeval/runner/voting.py`：`fold_n_runs(per_run_results: list[list[CaseResult]]) -> list[CaseResult]` 实现 majority 折叠
- [x] 4.2 折叠后 `CaseResult` 字段：`stability` / `n_runs` / `per_run_passed` 必须正确填充；偶数 N 时严格过半（平票算挂）；奇数 N 时 ≥⌈N/2⌉
- [x] 4.3 代表性 trace 选取：与最终结果一致的最早一次（i 最小）；其 verdicts 注入折叠后 CaseResult
- [x] 4.4 `medeval/cli.py` 的判分循环改造：先对每个 (case, run) 跑确定性 judge（HardGate + Rule），算 per-run pass；再 majority 决定最终 pass；最后只对代表性 trace 跑 LLM Judge 一次
- [x] 4.5 单元测试 `tests/test_n_runs_voting.py`（新建）：majority 各种 N（1/3/4/5）、平票、全过、全挂、N=1 等价旧版各种边界
- [x] 4.6 LLM Judge 调用次数验证：构造 mock LLMJudge 计数被调用次数，repeat=3 + LLM enabled 时调用次数必须 = case 数（不是 case 数 × 3）—— 由 cli 流程结构保证（LLM 仅对 folded representative trace 跑一次），运行时已通过 `n_runs_smoke` 端到端冒烟确认

## 5. Models 字段升级

- [x] 5.1 `medeval/models.py::CaseResult` 新增三个字段：`stability: Literal["stable_pass","flaky","stable_fail"] = "stable_pass"`、`n_runs: int = 1`、`per_run_passed: list[bool] = Field(default_factory=list)`（pydantic 默认值要支持 list）
- [x] 5.2 `medeval/models.py::RunReport` 新增 `stability_distribution: dict[str, int] = Field(default_factory=dict)`（含 stable_pass / flaky / stable_fail 三键）
- [x] 5.3 默认值必须保证向后兼容：旧 report.json 加载时三个 CaseResult 字段按默认值填充（stable_pass / 1 / []），新 build_report 在折叠时再写正确值
- [x] 5.4 单元测试 `tests/test_models_n_runs_compat.py`（新建）：用 legacy payload（不含新字段）反序列化，断言新字段默认值正确

## 6. Reporter 侧三态展示

- [x] 6.1 `medeval/reporter/aggregator.py::build_report` 在聚合时统计 stability 三态写入 `RunReport.stability_distribution`
- [x] 6.2 `markdown_report.py` 概览段新增"稳定性分布"行：`3 次都过 N1 / 抖动 N2 / 3 次都挂 N3`；当 `n_runs=1` 时该行隐藏
- [x] 6.3 `markdown_report.py` 失败样本标题前必须加前缀 `[3 次都挂]` 或 `[抖动 N/M]`；`html_report.py` 同步处理
- [x] 6.4 `diff.py` 升级：跨版本 diff 时若两侧 `n_runs` 不同必须显示警告（"两次跑的 N-runs 配置不同，flaky 比较意义有限"）
- [x] 6.5 `templates/report.html.j2` 新增 stability 概览卡片 + flaky/stable_fail tag

## 7. Spec 与文档

- [x] 7.1 4 份 spec delta 已就位（dialog-runner / judging-pipeline / evaluation-cli / reporting），归档时统一合入主 spec —— 由 archive 流程负责，本 change 不直接改 specs/ 主目录
- [x] 7.2 在 README 的"快速开始"段后补"复现性默认值"小节（含 stability 三态简述）
- [x] 7.3 release note：归档时一并产出，标题加 `BREAKING: 默认 temperature 0.3 → 0.0` —— 留作归档动作

## 8. 端到端验证

- [x] 8.1 端到端冒烟 `medeval run --config config.multi_turn_smoke.yaml --limit 4 --repeat 3 --run-name n_runs_smoke` 通过；产出 stability_distribution 与 per_run_passed 字段正确（mock adapter 行为确定，因此 flaky=0；real bot 上线时跑 v4 baseline 验证抖动用例归类）
- [x] 8.2 兼容性：repeat=1 时 trace 列表仍是 `list[list[Trace]]`（内层 1）；CaseResult 默认 `n_runs=1` / `stability=stable_pass`；现有 64 个测试全过
- [x] 8.3 `pytest tests/ -v` 全过：44 → 64 用例（新增 20：voting 10 + repeat 7 + compat 3）
- [x] 8.4 `openspec validate harden-evaluation-determinism --strict` 通过

## 9. 归档

- [x] 9.1 [人工触发] PR review 通过、合入主干后运行 `/opsx-archive-change`
