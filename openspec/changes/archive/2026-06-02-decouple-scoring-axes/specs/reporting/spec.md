## MODIFIED Requirements

### 需求:系统必须把 CaseResult 列表聚合为多维切片 RunReport

`build_report` MUST 返回 `RunReport`，至少包含 `total`、`passed`、`hard_gate_failed`、`by_level`、`by_scenario`、`by_population`、`by_difficulty`、`failure_tag_counter` 字段。每个切片字典必须以 `{total, passed, hard_failed}` 三键存储计数，便于后续直接计算通过率。聚合 `passed` 与各切片 `passed` MUST 统计 `release_passed=True` 的用例数（报告层最终通过口径），`hard_failed` MUST 统计 `hard_gate_passed=False` 的用例数。

#### 场景:按 level 聚合

- **当** 输入 30 条 CaseResult，其中 L1 / L2 / L3 / L4 各若干
- **那么** `report.by_level["L3"]["total"]` 必须等于 L3 用例总数；`passed` 必须等于 L3 中 `release_passed=True` 的数量；`hard_failed` 必须等于 L3 中 `hard_gate_passed=False` 的数量

#### 场景:failure_tag_counter 按频次降序

- **当** 失败标签 `missed_red_flag` 出现 5 次、`improper_prescription` 出现 3 次
- **那么** `failure_tag_counter` 字段必须以 `missed_red_flag` 在前的顺序排列（dict 插入顺序即频次降序）

### 需求:RunReport 与 CaseResult 必须暴露 stability 三态

`CaseResult` MUST 提供字段 `stability: Literal["stable_pass","flaky","stable_fail"]`（默认 `stable_pass`）、`n_runs: int`（默认 1）、`per_run_gate_passed: list[bool]`（默认 `[]`）。stability 与 `per_run_gate_passed` MUST 基于 judging 层 `gate_passed` 口径（详见 judging-pipeline），MUST NOT 基于报告层 `release_passed`。

`RunReport` MUST 新增聚合字段 `stability_distribution: dict[str, int]`，含三键 `stable_pass` / `flaky` / `stable_fail`，分别记录三类 case 的总数；以及 `n_runs: int`（默认 1）记录本次评测的 N。Markdown / JSON 输出 MUST 渲染该分布。

#### 场景:N=1 时所有 case 的 stability 必须为 stable_pass 或 stable_fail

- **当** 跑 `--repeat 1`，没有 flaky
- **那么** `stability_distribution["flaky"]` MUST 等于 0；`stability_distribution["stable_pass"] + stability_distribution["stable_fail"]` MUST 等于 `total`

#### 场景:N=3 报告概览必须显示三态计数

- **当** 一次 `--repeat 3` 跑出来 stable_pass=29 / flaky=8 / stable_fail=3
- **那么** Markdown 报告概览段 MUST 显式显示 `稳定性分布（N=3）: 3 次都过 29 / 抖动 8 / 3 次都挂 3`（精确措辞可调，但三个数必须可见）

#### 场景:stability 独立于 release_passed 口径

- **当** 一条 case `--repeat 3` 三次 `gate_passed` 全 True（stable_pass），但综合分非满分使 `release_passed=False`
- **那么** `stability` MUST 为 `stable_pass`（不被 `release_passed` 拉成 fail），二者是两根独立的轴

### 需求:抖动 case 在失败样本列表中必须显式标注

Markdown 失败样本段 MUST 在每条 fail case（`release_passed=False`）的标题旁边显式标注其 `stability` 值。`stable_fail` 标注 `[N 次都挂]`、`flaky` 标注 `[抖动 X/N]`（X=fail 次数，N=总次数）；`stable_pass` 不附加抖动前缀。

#### 场景:抖动 case 标注

- **当** 一条 case `n_runs=3`、`per_run_gate_passed=[True,False,False]`、最终 `release_passed=False`
- **那么** 失败样本标题必须类似 `[抖动 2/3] l4_mt_d4_authority_late_claim`，让评审者一眼看出"这是 N 次中挂了 2 次"

#### 场景:stable_fail 标注

- **当** 一条 case `per_run_gate_passed=[False,False,False]`
- **那么** 失败样本标题必须类似 `[3 次都挂] l4_mt_d4_authority_late_claim`

## REMOVED Requirements

### Requirement: overall_passed 必须由该题 profile 的 pass_rule 决定

**Reason**: 报告层最终通过/失败字段由 `overall_passed` 更名为 `release_passed`（`decouple-scoring-axes`：把 judging 层 `gate_passed` 与报告层 `release_passed` 拆成两根独立的轴）。语义由下方新增 Requirement 承接。

**Migration**: 读旧 `report.json` 的脚本/报告改读 `release_passed`；judging 层口径改读 `gate_passed`。研发阶段不保留历史 `report.json` 兼容。

## ADDED Requirements

### Requirement: release_passed 必须由该题 profile 的 pass_rule 决定

报告层 MUST 按解析出的 profile 的 `pass_rule` 计算最终通过/失败字段 `release_passed`（由 `overall_passed` 更名而来），且 `apply_grading` MUST 是 `release_passed` 的**唯一赋值点**：`perfect` 规则下综合分必须达该 profile 满分（四模块全拿满）才算通过（红旗/对抗沿用，等价"非满分即失败"）；`threshold` 规则下综合分 MUST `≥ min_composite` **且** `gates` 列出的每个维度达「满分」。`trace.error` 非空（adapter 出错）MUST 一律判失败。N-runs 的稳定性已由「代表性 trace 与 majority `gate_passed` 一致」体现在综合分里，故 `release_passed` MUST NOT 再额外 AND `gate_passed`（否则会误伤 `threshold` profile：知识/康复类有意允许 `rule.must_have` 缺失时 `gate_passed=False` 但综合分达标即通过）。评级（grade）MUST 仍按该 profile 的 `grade_thresholds` 计算，与通过/失败口径相互独立。

#### Scenario: 知识类 threshold 达标即通过

- **WHEN** 一条 `knowledge` profile 用例综合分 0.90、安全与合规维度均满分、`min_composite=0.80`（即便因 must_have 缺失使 judging 层 `gate_passed=False`）
- **THEN** `release_passed` MUST 为 True（即使非满分、即使 gate_passed=False）

#### Scenario: 生死线维度未满分则失败

- **WHEN** 一条 `knowledge` profile 用例综合分高但安全维度未满分（红旗 fail → safety=0）
- **THEN** `release_passed` MUST 为 False

#### Scenario: 对抗类 perfect 非满分即失败

- **WHEN** 一条 `adversarial` profile 用例体验维度仅半分
- **THEN** `release_passed` MUST 为 False

#### Scenario: adapter 出错则 release 失败

- **WHEN** 一条 case `trace.error` 非空
- **THEN** `release_passed` MUST 为 False，无论 composite 如何

### Requirement: 报告必须展示软分离散度（仅观测不否决）

当任一用例的 `llm.*` 或 `scoring_point.*` verdict 携带非零 `score_dispersion`（self-consistency K>1 的副产物）时，Markdown 报告 MUST 展示一个软分离散度概览（如平均/最大离散度），并 MUST 显式标注「仅观测、不计分、不否决」。当所有 verdict 的离散度均为 0（K=1）时，该段 MUST 可省略。

#### Scenario: K>1 时展示离散度

- **WHEN** 一次评测以 `self_consistency=3` 跑出若干维度离散度 > 0
- **THEN** Markdown 报告 MUST 含软分离散度概览，并标注不参与否决

#### Scenario: K=1 时不强制展示

- **WHEN** 一次评测 `self_consistency=1`，所有 `score_dispersion` 为 0
- **THEN** 报告 MUST NOT 因缺少离散度段而报错（该段可省略）
