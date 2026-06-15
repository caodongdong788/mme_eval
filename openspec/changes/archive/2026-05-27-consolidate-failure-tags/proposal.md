## 为什么

`failure_tags` 是评测框架的"产品语言"——报告里的 Top 失败标签、版本 diff 中的归因、未来 P3 人审界面的过滤维度，都依赖它。但目前它在三个来源之间各说各话：

- **README** 承诺 12 个标签，其中 5 个（`medical_hallucination` / `over_refusal` / `dialog_break` / `tool_misuse` / `empathy_miss`）**从未被任何 Judge 实际 emit**——对外是空头支票。
- **YAML 用例**的 `failure_tags_candidates` 引用了 3 个完全不存在的标签（`prompt_injection_success` / `safety_violation` / `privacy_violation`），写完没人提醒"这个 Judge 当前不识别"。
- **Judge 代码**自己悄悄 emit 了 README 未公开的 `constraint_violation` 与 `adapter_error`。

根因：标签是 **module-level 字符串字面量**。写错没人发现，新增没有契约，对外清单靠手维护文档。

P1 阶段即将把 LLM-as-Judge 默认开启、并启用版本 diff——届时"标签集"必须稳定且可机器对齐，否则跨版本归因不可信。趁还没大规模引用，现在收敛代价最小。

## 变更内容

- **新增** `FailureTag` 枚举（`models.py`），作为系统中所有失败归因标签的单一信任源。
- **修改** 所有 Judge（`HardGateJudge` / `RuleJudge` / `LLMJudge` / `aggregator`）emit 时改用 `FailureTag` 成员而非字符串字面量；`JudgeVerdict.failure_tags` 与 `CaseResult.failure_tags` 字段类型保持 `list[str]`（序列化兼容），但运行期取值必须来自 Enum。
- **修改** `TestCase.failure_tags_candidates` 字段类型由 `list[str]` 改为 `list[FailureTag]`，由 Pydantic 在加载阶段校验。
- **新增** 在 `models.py` 中标注每个 `FailureTag` 成员的 `dimension`（语义分类）和 `description`，作为对外文档的真正信任源。
- **新增** 一个生成 README 标签清单的脚本钩子（或直接由 Enum docstring 渲染），消除"README 与代码漂移"。
- **BREAKING**（用例侧）：YAML 中含有未声明的 `failure_tags_candidates` 取值的用例必须显式迁移；本次提案随附迁移映射表（见 design.md）。

## 功能 (Capabilities)

### 新增功能

无（不引入新 capability）。

### 修改功能

- `judging-pipeline`: 失败标签从约定俗成的字符串列表升级为受控 Enum，对 emit 与匹配做强约束。
- `case-schema-and-loader`: 用例侧 `failure_tags_candidates` 增加机器可验证的取值约束。

## 影响

- **代码**: `medeval/models.py`（新增 Enum）、`medeval/judges/{hard_gate,rule,aggregator,llm}.py`（emit 改 Enum）、`medeval/loader.py`（无变化，靠 Pydantic 校验自动生效）。
- **用例 YAML**: 共 ~30 条用例（主要是 `cases/L4_adversarial/adversarial.yaml`）需迁移到新词表。
- **报告**: 现有 `report.json` 中标签字符串保持不变（向后兼容），但**未来生成**的报告中标签集合稳定。
- **README**: 失败归因标签段落以脚本或手工方式与 Enum 对齐。
- **依赖**: 无新增依赖。
- **CI**: 启动用例加载时如发现非法 candidate 会抛错，原本"宽松通过"的用例会立刻变红，需在合入前集中清理。
