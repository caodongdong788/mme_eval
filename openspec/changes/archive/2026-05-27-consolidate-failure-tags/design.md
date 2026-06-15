## 上下文

P0 阶段为了快速跑通流程，所有失败标签都是 hard-coded 字符串：

```text
医疗咨询用例 ──┐
              │
              ▼
   ┌─────────────────────┐
   │  Judge (字符串字面量)│ ──► JudgeVerdict.failure_tags: list[str]
   └─────────────────────┘
              │
              ▼
   ┌─────────────────────┐
   │  Aggregator (set 去重)│ ──► CaseResult.failure_tags: list[str]
   └─────────────────────┘
              │
              ▼
        report.json (字符串排序后写出)
```

这种设计有三个集中度问题：

1. **写入侧 (Judge emit)** 没有词表约束。HardGateJudge 写 `"missed_red_flag"`，RuleJudge 写 `"constraint_violation"`，新加一个 Judge 时没有任何机制提示"应该复用哪些已有标签"。
2. **声明侧 (YAML failure_tags_candidates)** 没有词表约束。用例作者写下 `prompt_injection_success` 当作"我希望命中这个标签"，但运行时这个标签永远不会被 emit——属于影子期望。
3. **消费侧 (Reporter / Diff)** 把它当字符串聚合。一旦词表漂移（重命名、合并、拼写），跨版本对比中"同一个失败"被算成不同标签。

P1 即将启用"与上版本 diff"作为默认 reporter 功能，这个不稳定的"产品语言"问题会立刻被放大。

## 目标 / 非目标

**目标：**

- 把"系统中可能出现的 failure_tags 全集"用代码表达（Enum），让 IDE / lint / Pydantic 三方都能在编写阶段发现错误。
- 给每个标签附上 `dimension`（红旗 / 处方 / 合规 / 问诊 / 共情 / 对话 / 系统）和人类可读 `description`，把 README 失败归因段落从手维护文档升级为"由代码生成的"对外契约。
- 在用例加载阶段强制校验 `failure_tags_candidates`，把"用例对 Judge 的隐性期望"显式化。
- 保留 JSON 报告字段类型为 `list[str]`，**不破坏现有 report.json 的反序列化**——使用者拿旧报告做 diff 时不会因为字段类型变了而失败。

**非目标：**

- **不**改 `failure_tags` 的语义触发条件（例如什么时候打 `missed_red_flag` vs `under_referral`）。这是话题 3 才会触碰的范畴。
- **不**为标签建立"维度 → 标签 → 触发条件"三层模型（先前探索的方案 C），保持范围最小。
- **不**给每条标签建立 i18n（多语言描述）；P0/P1 单中文够用。
- **不**改 LLM-as-Judge 的标签输出格式（LLM Judge 当前不打 failure_tags，未来开启时再扩）。

## 决策

### 决策 1：用 `str, Enum` 还是 `enum.StrEnum`？

选 `class FailureTag(str, Enum)`（兼容 Py3.10）。Py3.11+ 才有原生 `StrEnum`；项目 `requires-python=">=3.10"` 不能用。

```python
class FailureTag(str, Enum):
    MISSED_RED_FLAG = "missed_red_flag"
    UNDER_REFERRAL = "under_referral"
    ...
```

**替代方案**：用 `Literal["missed_red_flag", "under_referral", ...]`。否决理由：无法附加 description / dimension 元数据。

### 决策 2：标签元数据怎么放？

每个 Enum 成员上挂一个 dataclass：

```python
@dataclass(frozen=True)
class _TagMeta:
    dimension: str   # "red_flag" / "prescription" / "compliance" / "communication" / "system"
    description: str

_TAG_META: dict[FailureTag, _TagMeta] = {
    FailureTag.MISSED_RED_FLAG: _TagMeta(
        dimension="red_flag",
        description="红旗症状未触发紧急/转诊建议",
    ),
    ...
}
```

**替代方案**：把 metadata 作为 Enum 子类的属性。否决理由：Pydantic 序列化时会出现尴尬的"是 Enum 还是 dict"问题，简单字典更可靠。

### 决策 3：序列化时保留字符串还是改为 Enum？

`JudgeVerdict.failure_tags` 与 `CaseResult.failure_tags` 类型保持 `list[str]`，使用方在 emit 时传 `FailureTag.X.value`（其实 Enum 是 str 的子类，传 `FailureTag.X` 也可，自动序列化为 string）。

理由：
- 现有 outputs/*.json 全部是字符串数组。改成 Enum 后 pydantic 反序列化时如果没注册转换器会失败。
- 把"边界严格 + 内部宽松"的好处保留：在 emit 一侧（生产）严格，在反序列化一侧（消费）宽松。

### 决策 4：用例 `failure_tags_candidates` 改成强类型

`TestCase.failure_tags_candidates: list[FailureTag] = Field(default_factory=list)`。Pydantic v2 会在加载 YAML 时自动校验每个字符串是否在 Enum 取值中。

**迁移映射**：

| 现有取值 | 新映射 | 备注 |
|-|-|-|
| `prompt_injection_success` | `CONSTRAINT_VIOLATION` + 在 case `tags` 中加 `adversarial` | 用例语义保留在 tags 而非 failure_tags |
| `safety_violation` | 拆为 `IMPROPER_PRESCRIPTION` 或 `MISSED_RED_FLAG` | 视具体用例语境而定 |
| `privacy_violation` | 暂归 `CONSTRAINT_VIOLATION` | P2 隐私维度 Judge 上线后再细分 |

### 决策 5：README 怎么和 Enum 对齐？

两种路线，提案倾向 **B**：

- A. 手维护 + CI lint：写一个 pytest 用例，检查 README 标签段落和 Enum 成员一致。
- B. **自动生成**：写一个 `python -m medeval.docs.gen_failure_tags > README_FAILURE_TAGS.md` 脚本，README 用 `<!-- AUTO-GENERATED -->` 标记的段落由它覆盖。

B 的好处是不再需要纪律，且 PR review 时一眼能看出标签集变化。

## 风险 / 权衡

- **风险**：用例 YAML 迁移可能踩到测试用例集变红 → CI 阻塞。
  **缓解**：tasks.md 把"迁移 YAML"放在"打开 Pydantic 校验"之前，且写一个一次性脚本扫描所有 cases 自动报需要迁移的位置。

- **风险**：FailureTag 是 `str` 子类，json.dumps 时会输出 string 没问题，但 pydantic v2 在反序列化 `list[str]` 字段时拿到包含全是 Enum 的 list 也工作正常；不过测试要覆盖。
  **缓解**：tasks.md 增加单测"Enum 与 list[str] 在 Pydantic 双向序列化的兼容性"。

- **权衡**：把 README 改成自动生成的段落，对作者写作风格有约束（不能在该段落中插入手写说明）。这是值得的，因为该段落本质就是"枚举对照表"。

- **风险**：未来 LLM-as-Judge 开始 emit 自定义 failure_tags 时，新增标签会需要先改 Enum 再合用例。
  **缓解**：这是预期的工作流——"标签是产品语言"意味着所有人共享同一份词表，这就是收益。

## 迁移计划

1. 引入 `FailureTag` Enum，**先不改任何 emit 处**（即新代码与旧字符串并存）。
2. 写迁移扫描脚本，输出所有 YAML 里需要改的位置 + 推荐映射。
3. 一次 PR 批量改 YAML + Judge emit 改 Enum + 打开 Pydantic 校验。
4. 把 README 失败归因段落标记 `<!-- AUTO-GENERATED -->` 并接入生成脚本。
5. 把 outputs/*.json（历史报告）保留在原仓库以备 diff，**不**做向前迁移（旧字符串值会自动落入 Enum 的 `_value_map`）。

### 决策 6：`dimension` 用字符串元数据，不独立 Enum

`_TagMeta.dimension` 取 `Literal["red_flag", "prescription", "compliance", "communication", "system"]`，**不**升级为独立 `Dimension` Enum。

理由：

- 标签总数 P0/P1 阶段就 ~12 个、dimension ~5 个，常量空间小；Enum 双层结构带来的"防错"收益被 `Pydantic + Literal` 类型检查抵消。
- 字符串型 dimension 序列化无歧义；独立 Enum 在 `model_dump_json` 时容易出现"是 Enum 还是 str"的角度尴尬。
- Py 3.10 不能用原生 `StrEnum`，独立 Enum 需要 `class Dimension(str, Enum)` 双层模板，反而比 `Literal` 啰嗦。

未来若要做"按 dimension 切片报告"（P3 人审界面期望）再升级；那时已经有了完整的真实使用数据来决定 dimension 的取值范围。

### 决策 7：LLM 相关 failure_tags 本次只**预留 Enum 成员**，不动 LLMJudge emit 路径

`FailureTag` 必须新增 `EMPATHY_MISS` / `POPULATION_BLIND` / `DIFFERENTIAL_NARROW`（以及 `MEDICAL_HALLUCINATION` / `OVER_REFUSAL` / `DIALOG_BREAK` / `TOOL_MISUSE`，对应 README 已对外宣称但未实现的标签）作为枚举成员，但**本提案不让 LLMJudge 在判分时实际 emit 这些标签**。

理由：

- LLM emit 标签需要改 `_PROMPT_TEMPLATE` 输出格式（要求 LLM 返回 `{"scores": {...}, "reasons": {...}, "tags": [...]}`），并需要把 LLM 返回的字符串校验为 `FailureTag`——这两件事的失败模式与本提案的"词表收敛"完全不同。
- LLM 默认开启在 P1 路线图上，是独立的工程动作；混在本提案里会让 review 范围爆炸。
- 但**先预留 Enum 成员**有两个好处：(1) 用例侧 `failure_tags_candidates` 可以合法引用这些标签（避免 README 二次撒谎）；(2) 未来 LLMJudge emit 上线时词表已经稳定，不需要再做一次"标签词表迁移"。

待独立提案：`llm-judge-emit-failure-tags`，预计与"LLM 默认开启"同期。

## Open Questions

（无；上述决策已闭合最初的两个 Open Q）
