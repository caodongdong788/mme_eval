## 修改需求

### 需求:Verdict 必须以失败标签驱动归因分析

每个 Verdict 在 fail 时必须填入 `failure_tags`，其取值必须来自 `medeval.models.FailureTag` 这个 `(str, Enum)` 枚举。该枚举是系统中 failure_tags 的**单一信任源**：Judge 不得 emit 不在枚举中的字符串，且每个枚举成员必须附带 `dimension` 与 `description` 元数据。`JudgeVerdict.failure_tags` 与 `CaseResult.failure_tags` 字段的序列化类型保留为 `list[str]`，以保持与历史 report.json 的兼容性；Judge 在运行期 emit 时必须传 `FailureTag` 成员而非裸字符串。报告侧据此聚合 Top 失败标签。

#### 场景:多个 fail 必须汇集到 failure_tags

- **当** 一条用例既漏红旗、又含确诊措辞
- **那么** `CaseResult.failure_tags` 必须同时含 `FailureTag.MISSED_RED_FLAG.value` 与 `FailureTag.OVER_DIAGNOSIS.value`（即字符串 `"missed_red_flag"` 与 `"over_diagnosis"`）

#### 场景:Judge 必须使用 Enum 成员 emit 标签

- **当** 开发者在 Judge 代码中尝试 `failure_tags=["typo_tag"]`
- **那么** 静态类型检查（mypy / pyright）或单测必须能在合入前发现该字符串不在 `FailureTag` 中，禁止合入

#### 场景:历史 report.json 仍可被反序列化

- **当** 加载评测前的 outputs/doubao_baseline/report.json（其中 failure_tags 为字符串数组）
- **那么** `RunReport.model_validate_json(...)` 必须仍能成功，已存在的标签值即便对应 Enum 已变更名称也不应抛错（向前兼容历史报告）

### 需求:Aggregator 必须把多 Judge 输出合并为统一 CaseResult

`judge_all(case, trace, judges)` 必须并行运行所有 judge（asyncio.gather），把 verdicts 拼到一起，并按以下规则计算结论：

1. `hard_gate_passed` = 所有以 `hard_gate.` 开头的 verdict 都 passed（若无硬门槛则视为 True）
2. `overall_passed` = `hard_gate_passed` AND 所有以 `rule.` 开头的 verdict 都 passed AND `trace.error is None`
3. `soft_score` / `soft_score_max` 累加自所有 `llm.` 开头的 verdict
4. `failure_tags` = 所有 verdict 的 `failure_tags` 去重排序集合，其每个元素必须是 `FailureTag` 中某个成员的 `value`；若 `trace.error` 非空必须额外追加 `FailureTag.ADAPTER_ERROR.value`

#### 场景:trace 出错时必须整体 fail

- **当** Runner 给出的 `trace.error` 非空（adapter 三次都超时）
- **那么** 不管硬门槛如何，`overall_passed` 必须为 False，failure_tags 必须包含 `"adapter_error"`（来自 `FailureTag.ADAPTER_ERROR`）

#### 场景:单个 judge crash 不能拖垮其他 judge

- **当** RuleJudge 由于 bug 抛出未捕获异常
- **那么** Aggregator 必须把它包装成一条 `rule.error` 的 fail verdict，HardGate 与 LLMJudge 的结果必须照常出齐

#### 场景:无硬门槛、无规则、纯软分用例

- **当** 用例只声明 rubric（如纯共情评测），未声明 hard_gates 与 expected_behavior
- **那么** `hard_gate_passed` 必须为 True，`overall_passed` 也为 True（不被软分拉低），soft_score 反映 LLMJudge 的分数

## 新增需求

### 需求:FailureTag 枚举必须为每个标签提供 dimension 与 description 元数据

`FailureTag` 必须以受控词表的形式存在于 `medeval/models.py`。每个枚举成员必须附带：

- `dimension`：取值范围限定为 `red_flag`、`prescription`、`compliance`、`communication`、`system` 中之一，用于报告聚合与人审界面的二级分类。
- `description`：≤80 字符的中文描述，作为面向产品/临床读者的标签说明。

枚举必须暴露便捷访问方式（如 `FailureTag.MISSED_RED_FLAG.dimension`）。系统中任何用到 failure_tags 的位置（README、报告聚合、Judge emit、用例 candidate）都必须以该枚举为单一信任源。

#### 场景:每个枚举成员都有完整元数据

- **当** 单测遍历 `FailureTag` 的所有成员
- **那么** 每个成员的 `dimension` 必须在白名单内、`description` 必须非空且长度 ≤80

#### 场景:README 必须由枚举自动生成对应段落

- **当** 在 CI 中运行 `python -m medeval.docs.gen_failure_tags` 并把输出写入 README 的 `AUTO-GENERATED` 标记段
- **那么** 与 git 仓库中已提交的 README 段落 diff 必须为空；任何对 Enum 的新增/删除/重命名都必须随 PR 更新 README

#### 场景:Judge 拿到 dimension 用于分类

- **当** 报告聚合需要按 dimension 切片（如 P3 阶段"红旗失败数 / 处方失败数"分项）
- **那么** 必须能通过 `FailureTag(value).dimension` 直接获取分类，不允许在报告层再硬编码标签到 dimension 的映射表
