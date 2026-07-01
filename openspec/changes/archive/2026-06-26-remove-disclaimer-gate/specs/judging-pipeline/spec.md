## MODIFIED Requirements

### Requirement: 系统必须提供以 `BaseJudge` 为根的可组合 Judge 抽象

系统 MUST 定义 `BaseJudge`，其 `judge(case, trace) -> list[JudgeVerdict]` 必须是异步抽象方法（单个 judge 可返回多个 verdict）。基类必须提供 `_last_reply` / `_full_reply` 等便利方法以便子类读取 assistant 回复（按 role=assistant 拼接）。

#### Scenario: HardGate Judge 只返回红旗与处方边界 verdict

- **WHEN** HardGateJudge 处理一条用例
- **THEN** 它 MUST 返回名为 `hard_gate.red_flag` / `hard_gate.no_prescription` 的 Verdict
- **AND** 它 MUST NOT 返回 `hard_gate.disclaimer` Verdict

### Requirement: Verdict 必须以失败标签驱动归因分析

每个 Verdict 在 fail 时 MUST 填入 `failure_tags`，其取值必须来自 `medeval.models.FailureTag` 这个 `(str, Enum)` 枚举。该枚举是系统中 failure_tags 的单一信任源：Judge 不得 emit 不在枚举中的字符串，且每个枚举成员必须附带 `dimension` 与 `description` 元数据。新评测 MUST NOT emit `disclaimer_miss`；历史 report.json 中已有的字符串标签仍可作为普通字符串反序列化，以保持向前兼容。`JudgeVerdict.failure_tags` 与 `CaseResult.failure_tags` 字段的序列化类型保留为 `list[str]`。

#### Scenario: 历史免责声明 verdict 不影响聚合事实

- **WHEN** 聚合逻辑收到历史 `hard_gate.disclaimer` 且 `passed=False`
- **THEN** `hard_gate_passed` MUST 仍只由当前有效 hard gate 决定
- **AND** `compliance_failed` MUST 保持 False，报告合规分不得因该历史 verdict 归零

### Requirement: FailureTag 枚举必须为每个标签提供 dimension 与 description 元数据

`FailureTag` MUST 以受控词表的形式存在于 `medeval/models.py`。每个枚举成员必须附带：

- `dimension`：取值范围限定为 `red_flag`、`prescription`、`communication`、`system` 中之一，用于报告聚合与人审界面的二级分类。
- `description`：≤80 字符的中文描述，作为面向产品/临床读者的标签说明。

枚举必须暴露便捷访问方式（如 `FailureTag.MISSED_RED_FLAG.dimension`）。系统中任何用到 failure_tags 的位置（README、报告聚合、Judge emit、用例 candidate）都必须以该枚举为单一信任源。`disclaimer_miss` MUST NOT 出现在当前 FailureTag 词表、README 自动生成段或新用例候选标签中。
