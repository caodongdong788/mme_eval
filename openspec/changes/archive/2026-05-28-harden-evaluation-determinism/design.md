## Context

`add-multi-turn-evaluation` change 落地后跑了 3 次同套 40 case 的 live run，实测发现 8/40 = 20% case 在跨次跑中 pass/fail 翻动。这导致评测报告的"通过率"在 ±10pp 范围内随机抖动，让"区分版本好坏"的核心目标失效。本 change 的目标是把"评测结果可重现"作为框架的硬约束，而不是依赖运气。

利益相关方：
- 评测框架维护者（确保 N-runs 在工程上可控）
- 模型迭代方（依赖稳定信号做 A/B 决策）
- 临床评审者（不希望同一份 case 在不同 run 给出矛盾结论）

## Goals / Non-Goals

**Goals:**

- 让"复现"是默认姿态：未配 temperature 时取 0.0；用户要采样必须显式声明 `temperature: 0.3`
- 提供一阶抗噪机制：N-runs majority voting，N=3 时把 1 票噪声压到 0
- 报告侧明确暴露 stability：让"3 次都过的 29 条"和"抖动的 8 条"在报告概览里就能区分开
- 控制成本：N-runs 不应让 LLM judge 调用也 ×N（开销最大的部分）

**Non-Goals:**

- 不在 framework 层做"贝叶斯置信区间"等高阶统计——majority 是足够实用的一阶兜底
- 不强制所有 run 都用 `repeat=3`——日常迭代用 1，关键 baseline 用 3，由用户决定
- 不改 LLM judge 内部的 sampling（temperature 已是 0.0）；只控 adapter 端
- 不解决"同一条 case 在两个温度下结果不同"的版本对比问题——这是另一种 fingerprint，本 change 之后再考虑

## Decisions

### 决策 1：默认 `temperature=0.0`，采样要显式开启

**选择**：所有内置 adapter（openai_compat / http）的"未配 temperature 时默认值"统一改为 `0.0`。

**为什么**：
- 评测框架的默认姿态应该是"复现优先"。"探索 / 创意"不是评测的诉求
- 现有 config.yaml 显式写了 `temperature: 0.3` 的不受影响（显式优先级最高）
- 把噪声源头堵住，比下游加 N-runs 更省钱

**取舍**：默认温度变化是 breaking change（历史报告不可与新报告直接对比）。必须在 README / changelog 显式标注，并在 `diff_runs` 输出里打 fingerprint 警告（历史 report 的 `adapter_config_hash` 缺失）。

**Alternative considered**：保持 0.3，靠 N-runs 在下游消除噪声。被否：成本是 0.3 → 0.0 的几十倍，且无法消除"温度本身设计为有方差"的语义错误。

### 决策 2：N-runs 用 majority voting，不用 strict / lenient

**选择**：N=奇数时"过半即过"；N=偶数时"严格过半"（平票算挂）。

**为什么**：
- majority 抗噪声最强：N=3 能消除 1 票噪声，N=5 能消除 2 票
- strict（全过才算过）会把"边缘 flaky 但不太严重"的 case 全部 dramatize 成 fail，过度悲观
- lenient（任一过即过）相当于让 bot 用最好的一次代表自己，过度乐观，违背"评测要看典型表现"的诉求
- majority 是工程上的甜蜜点

**取舍**：majority 不能消除"3 次都偶然过"或"3 次都偶然挂"的极端情况，但概率随 N 指数下降；N=3 时单次错误率 30% 的话，3 次都错的概率仅 2.7%，可接受。

**Alternative considered**：报告里同时显示 strict + lenient + majority 三个数。被否：信息过载，决策者要看一个数。最终决定 majority 是判定，但 stability 字段（stable_pass/flaky/stable_fail）让评审者仍能看到完整三态。

### 决策 3：LLM Judge 不重复调用，只对"代表性 trace"跑一次

**选择**：N-runs 中 adapter + HardGate + Rule 都跑 N 次，LLM Judge 只跑 1 次（针对代表性 trace）。

**为什么**：
- LLM Judge 是 token 消耗大头（multi-turn case 单次 prompt 数千 token），重复 N 次是数倍开销
- LLM Judge 自身已经设 `temperature=0.0`，本身就是确定性的，对同一 trace 重复调用没意义
- HardGate / Rule 都是确定性 judge，对同一 trace 重判结果一定相同；但因为 adapter 输出不同导致 trace 不同，所以这俩 judge 必须跑 N 次

**代表性 trace 的选取规则**：
1. 先按 majority 算出最终 pass/fail
2. 在 N 次中筛选与最终结果一致的 trace（pass→筛 N 次中 passed 的、fail→筛 failed 的）
3. 在筛出的 trace 里挑"verdict 配置出现频次最多"的那次；并列时取最早一次（i 最小）

**取舍**：LLM Judge 的 `multi_turn_consistency` 维度评分只反映代表性 trace 的表现，不反映 N 次的均值。我们认为这是可接受的——majority 已经把"是否通过"这个高阶信号确定下来，LLM 的细粒度评分只需要 explain why。

**Alternative considered**：LLM Judge 也跑 N 次取均分。被否：N=3 LLM 调用成本 ≈ 当前的 3 倍，对边际价值（细粒度评分变稳）的提升不值。

### 决策 4：N-runs 串行跑，不在单 case 内部并行

**选择**：N-runs 同一条 case 的 N 次 adapter 调用是顺序的，不并行；不同 case 之间仍按 `concurrency` 并行。

**为什么**：
- 大多数 chatbot adapter 对同一 session_id / 同一上下文的并发请求会撞 rate-limit
- 串行跑能控制 doubao 的 5 RPM / 10 RPM 之类的限流配额
- 对成本几乎无影响（concurrency=4 + repeat=3 时 throughput = 4，与 concurrency=4 + repeat=1 相同）

**取舍**：单条 case 的总耗时变成 ×N。对 40-case 全量评测，从 5 分钟涨到约 12 分钟，可接受。

**Alternative considered**：并行 N 次同一 case。被否：rate-limit 风险高、调试困难。

### 决策 5：`stability` 字段的命名与三态语义

**选择**：`stability ∈ {stable_pass, flaky, stable_fail}`。

**含义**：
- `stable_pass`：N 次都 `overall_passed=True`
- `stable_fail`：N 次都 `overall_passed=False`
- `flaky`：N 次中既有 pass 也有 fail（无论 majority 怎么判）

**为什么**：
- 这三态是评审者最关心的——`stable_*` 直接 trustable，`flaky` 标黄需要单独审查
- 命名借自 pytest-flaky 的语义，业界共识

**报告呈现**：markdown / HTML 概览表必须新增一列"稳定性分布 (stable_pass/flaky/stable_fail)"，例如 `29/8/3`。

### 决策 6：N=1 必须保持完全的旧版语义

**选择**：当 `repeat=1` 时（默认），所有新代码路径必须等价于旧逻辑；`stability` 永远填 `stable_pass`、`n_runs=1`、`per_run_passed=[overall_passed]`。

**为什么**：
- N-runs 是可选增强，不是强制升级。要让现有 CI / config 0 改动继续工作
- 测试覆盖：必须有一条测试保证 `repeat=1` 与旧版字节对齐（除新增的 stability/n_runs/per_run_passed 字段外）

## Risks / Open Questions

**风险 1：majority 对真 bug 的"3 次都过"误判**
真 bug 也可能在某次 sampling 下偶然产生合规输出。N=3 不能避免这种情况，但 N=5 能进一步降低概率。本 change 不强制 N=5，但在 docs 中说明"上线门禁建议 N≥5"。

**风险 2：温度从 0.3 → 0.0 后，部分 case 行为变化非"更确定"而是"系统性变差"**
某些 doubao endpoint 在 temperature=0.0 时表现反而劣化（已知现象）。缓解：在 changelog 里强调"切换默认温度后必须重跑 baseline"，并保留 config 显式覆盖能力。

**Open question：是否要支持"对部分 case 单独设 repeat"？**
比如对 multi-turn 用例统一 `repeat=3`、单 turn 用 `repeat=1`。当前 design 不支持 case-level override，由用户在 cases include 上分多次跑解决。等真有需求再加 `case.repeat` 字段（YAML 优先于 CLI）。

## Migration Plan

1. 默认温度变化必须在 README 显式注明并在 release note 强调；建议用户先用旧 config 跑一次 baseline 留底，再切到新版
2. 新增 CLI flag `--repeat N` 不加默认值（默认走 config，未配置时 1），保持向后兼容
3. JSON report schema 通过 pydantic 默认值向后兼容旧 report 加载（`stability` 默认 `stable_pass`、`n_runs` 默认 1、`per_run_passed` 默认空列表）
4. 推荐升级路径：dev → 默认 `repeat=1`；release 前的 baseline run → 显式 `--repeat 3`；正式上线门禁 → 显式 `--repeat 5`（在 config / CI workflow 里写死）
