## Why

`add-multi-turn-evaluation` 落地后做了 3 次同套用例的 live run（v1/v2/v3，每次 40 case，doubao + GPT-5.1 judge），实测稳定性数据是：

```
3 次都通过：29 条
3 次都失败： 3 条  ← 真 bug（l4_authority_late_claim 等）
跨次抖动  ： 8 条  ← 同一条 case 在不同 run 里 pass/fail 翻来翻去
```

**8/40 = 20% 的用例结果不稳定**，意味着评测报告的"通过率"在 ±10pp 范围内随机抖动。这把"评测能不能区分版本好坏"这件事直接打破——v1 报 87.5%、v2 报 80%、v3 报 82.5%，被测 bot 完全没变，差异全是 sampling 噪声。

根因有两层：
- L1 噪声：adapter 默认 `temperature=0.3`、top_p 默认未约束，单 turn 输出本身有方差
- L2 噪声：长对话 (depth=4/5) 里前轮微抖动级联放大后轮，多轮 case 噪声占比远高于单轮 case（实测：单 turn 抖动 ≈3%、5-turn 抖动 ≈25%）

为了让评测真的"可区分版本"，必须给框架装上抗噪声机制。

## What Changes

- 把所有内置 OpenAI-compat / HTTP adapter 的"未指定时默认 temperature"从 `0.3` 改为 `0.0`，让"复现"成为框架默认姿态而不是用户必须显式开启
- 新增 `--repeat N` CLI flag（也可在 config 里配 `run.repeat`），默认 `1`（即不重复，向后兼容），开启后框架对每条 case 跑 N 次 adapter 调用 + N 次 judge，得到 N 个 `CaseResult`
- 新增 `medeval/runner` 中的"N-runs voting aggregator"：把 N 个 `CaseResult` 折叠成一个最终 `CaseResult`，判定规则是 **majority pass**（N=3 时 ≥2 次过即过；N=5 时 ≥3 次过即过；N 偶数时严格"过半"，平票算挂）
- 报告侧新增 `stability` 三态字段：每条 case 标 `stable_pass` (N 次都过) / `flaky` (有 pass 有 fail) / `stable_fail` (N 次都挂)；markdown / 飞书报告概览必须显示三态分布
- LLM Judge 不重复调用：majority voting 只针对 adapter 调用 + 规则/硬门槛，LLM Judge 仍按"对最终的代表性 trace 跑一次"以控成本（代表性 trace 选择策略见 design.md）

## Capabilities

### Modified Capabilities

- `dialog-runner`：新增"N-runs 重复执行 + 折叠"约束。Runner MUST 接受 `repeat: int` 参数，对每条 case 顺序调用 adapter N 次得到 N 个 `ConversationTrace`。
- `judging-pipeline`：新增"majority voting aggregator"约束。Aggregator MUST 把 N 个 case-level `CaseResult` 按"过半数原则"折叠为一个最终 `CaseResult`，并保留 N 次原始 verdict 用于 stability 分类。
- `evaluation-cli`：新增 `--repeat N` 命令行参数；新增 `run.repeat` 配置字段。
- `reporting`：报告 schema 新增 `stability` 字段；markdown 概览必须显示 stable_pass / flaky / stable_fail 三类计数。

### New Capabilities

无。

## Impact

**受影响代码**

- `medeval/cli.py` —— 新增 `--repeat` flag、把 `run.repeat` 透传到 runner
- `medeval/runner/executor.py` —— `run_cases` 接受 `repeat` 参数，内部循环 N 次
- `medeval/runner/aggregator.py`（新建）—— `fold_n_runs(results: list[list[CaseResult]]) -> list[CaseResult]` 实现 majority voting
- `medeval/judges/aggregator.py` —— `judge_all` 不变；新增 `select_representative_trace` 工具用于 majority pass 后选 trace 喂 LLM Judge（选最常见 verdict 模式对应的 trace；并列时取最早一次）
- `medeval/models.py` —— `CaseResult` 新增 `stability: Literal["stable_pass","flaky","stable_fail"]` 字段（默认 `stable_pass`，N=1 时永远 stable_pass）；新增 `n_runs: int` 字段（默认 1）；新增 `per_run_passed: list[bool]` 字段（默认 `[True]`，长度恒等于 `n_runs`）
- `medeval/reporter/aggregator.py` + `markdown_report.py` + `html_report.py` + `json_report.py` —— 渲染 stability 三态
- `config.yaml` / `config.l1.yaml` / `config.multi_turn.yaml` —— 默认 `temperature: 0.0`；新增 `run.repeat: 1` 字段（向后兼容）
- `tests/test_n_runs_voting.py`（新建）—— 单元测试覆盖 majority 折叠逻辑

**不受影响**

- 单次跑（`repeat=1`）的行为完全与旧版一致：`stability` 恒为 `stable_pass`、`per_run_passed=[overall_passed]`
- HardGate / Rule / LLM Judge 各自的 fingerprint 不变（判分逻辑没动）
- 既有报告 JSON 通过 schema 默认值向前兼容（旧 report 加载时 `stability` 默认填 `stable_pass`）

**评测成本**

- `--repeat=1`：与旧版完全相同，0 增量
- `--repeat=3` 默认配置：adapter 调用 ×3、规则/硬门槛 judge ×3、LLM Judge ×1（用代表性 trace），整体延迟约 ×2.3，token 成本约 ×2.3
- 推荐使用模式：日常迭代 `repeat=1`、重要 baseline / 上线前 `repeat=3`

**默认温度变化的副作用**

- 把默认 `temperature=0.3 → 0.0` 后，**历史报告与新报告不可直接对比**（bot 输出分布变了）。`diff_runs` 不会自动检测温度变化，所以本 change 必须在 README 与 release notes 里显式标注"切换温度后请重跑 baseline"。
