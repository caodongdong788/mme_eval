## Context

`FailureTag` 是 `medeval/models.py` 里的受控词表，所有 Judge emit 失败原因都必须用它的 enum 成员。它的元数据 `_TagMeta` 现在只有两个字段：`dimension`（红旗/处方/合规/沟通/系统）和 `description`（一句长描述，例如 "红旗症状未触发紧急/急诊建议"）。

飞书报告 `medeval/reporter/markdown_report.py` 在两处直接渲染 `r.failure_tags`（来自 `CaseResult.failure_tags`，类型是 `list[FailureTag]`，因为 enum 继承自 `str` 所以渲染出来就是英文 `snake_case`）：

1. 概览段「失败归因 Top 标签」表（line 160~165）—— 整个表格 15 行 enum value，没有中文
2. 失败样本段每条 case 的 `**失败标签：** ...` 行（line 104）—— 用 `, ` 拼接

下游消费者：
- `excel_transcript.py` 把 failure_tags 写进 Excel 列（机器可读分析用）
- `report.json` `failure_tags` 数组（CI/diff 比对用）
- `gen_failure_tags.py` 读 enum 自动生成 README 失败标签清单

约束：v7 报告 / 历史报告对比 / `compare_runs` regression 都依赖 `failure_tags` 是 stable string id；不能把 enum value 改成中文。

## Goals / Non-Goals

**Goals:**
- 飞书 docx markdown 报告里的失败标签**只显示中文短词**（4~8 字），让产研同学读报告无心算成本
- 单一信任源：中文短标签和现有 `dimension` / `description` 一样存在 `_TAG_META` 里，新增成员时编译期就强制提供（沿用 `assert set(_TAG_META.keys()) == set(FailureTag)` 自检）
- 渲染层和数据层完全解耦：`report.json`、Excel transcript、CI 对比逻辑全部不变

**Non-Goals:**
- 不修改 `report.json` 的 `failure_tags` / `failure_tag_counter` 字段（仍是英文 enum value）
- 不修改 Excel transcript 里 failure_tags 列（导出物给下游分析脚本，保持英文 stable key）
- 不调整 `dimension` / `description` 现有语义（`description` 仍可在未来文档/工具 hover 中使用）
- 不引入 i18n 框架（只做中→中，没有英文界面需求；当前所有报告读者都是中文）
- 不改 `failure_tags_candidates` 用例 YAML 字段（用例侧仍写英文 enum value，与 schema 对齐）

## Decisions

### Decision 1：在 `_TagMeta` 加 `label_zh` 字段，而非沿用 `description`

**选择**：给 `_TagMeta` 加一个 `label_zh: str` 字段，4~8 字短词；现有 `description` 保留不动。

**为什么不直接用 `description`**：
- `description` 是一句完整说明（"给出具体药品+剂量/频次，越过处方边界"，22 字），塞进表格 `| 标签 | 次数 |` 第一列会撑爆飞书 docx 表格宽度
- `description` 失败样本段并列展示 2~3 个 tag 时（v7 实测 `constraint_violation, missed_red_flag` 这种）会变成长句拼接，可读性反而下降
- 短标签和长描述两个职责分离：短标签 = 表格/标题行渲染；长描述 = README 文档/未来 hover 提示

**短标签设计原则**：
- 4~8 字（飞书 docx 表格视觉舒适区间）
- 动宾或名词结构（"漏报红旗" / "越界处方" / "缺免责"）
- 与 `dimension` 维度对齐但更具体（同属 communication 维度的也要能区分）

完整短标签词表（提案阶段确定，实现阶段保持稳定）：

| 英文 enum value | 短中文 label | dimension |
|---|---|---|
| `missed_red_flag` | 漏报红旗 | red_flag |
| `under_referral` | 转诊不足 | red_flag |
| `improper_prescription` | 越界处方 | prescription |
| `over_diagnosis` | 越界确诊 | prescription |
| `disclaimer_miss` | 缺免责 | compliance |
| `inquiry_incomplete` | 问诊不足 | communication |
| `constraint_violation` | 触发禁词 | communication |
| `adapter_error` | 调用失败 | system |
| `empathy_miss` | 共情不足 | communication |
| `population_blind` | 人群盲区 | communication |
| `differential_narrow` | 鉴别窄 | communication |
| `medical_hallucination` | 医学幻觉 | communication |
| `over_refusal` | 过度拒答 | communication |
| `dialog_break` | 上下文断 | communication |
| `tool_misuse` | 工具误用 | system |

### Decision 2：渲染层用 `_tag_to_zh_label(tag_str)` helper 而非直接 `FailureTag(tag_str).label_zh`

**选择**：在 `markdown_report.py` 加 `_tag_to_zh_label(tag_str: str) -> str` helper：
```python
def _tag_to_zh_label(tag_str: str) -> str:
    try:
        return FailureTag(tag_str).label_zh
    except ValueError:
        return tag_str  # 历史 report.json 出现未知 tag 时降级显示原文
```

**理由**：
- 报告渲染要能消费**历史 report.json**（`compare_runs` regression / 重新生成 markdown）。历史报告里可能有当前 enum 已删除的 tag string，直接 `FailureTag(...)` 会抛 ValueError
- 给后续提案（`llm-judge-emit-failure-tags`）一个安全降级路径，新枚举成员上线前的报告也能渲染
- helper 集中后续语义微调（比如想把 dimension 也带上："[红旗] 漏报红旗"）

### Decision 3：Excel transcript 保持英文不变

**选择**：`excel_transcript.py` 的 failure_tags 列写英文 enum value，不渲染中文。

**理由**：
- Excel 是面向**下游分析脚本**的稳定 schema，不是给人读的报告。中文列值会让 pandas 分组、CI diff、外部 dashboard 集成全部要做翻译
- markdown 报告（人读）和 Excel（机读）渲染策略本来就分叉，这一点单测 (`test_excel_transcript.py`) 加 assert 锁定，避免未来改 markdown 时连带误改 Excel

### Decision 4：`gen_failure_tags.py` 同步用 `label_zh`

**选择**：自动生成的 `README.md` 失败标签清单从 `description` 一列扩展为 `label_zh` + `description` 两列（或行内并列）。

**理由**：README 是人读文档，与飞书报告口径一致；`label_zh` 当 anchor，`description` 当详情，方便用户从报告里看到"漏报红旗"立刻在 README 索引到详细解释。

## Risks / Trade-offs

| Risk | Mitigation |
|---|---|
| 短标签语义和 `description` 不一致（短标签太省略导致歧义） | 提案阶段一次性敲定全部 15 条短标签词表（见 Decision 1 表格）；实现阶段照搬，code review 阶段 designer 一遍 |
| 历史 report.json 重新渲染 markdown 时崩溃（未知 tag） | `_tag_to_zh_label` 降级到原文 (Decision 2)，加单测覆盖 |
| 未来增枚举成员忘了补 `label_zh` | 沿用 `_TAG_META` 完整性 assert：`set(_TAG_META.keys()) == set(FailureTag)`；测试再加一条 `all(meta.label_zh for meta in _TAG_META.values())` |
| 飞书 docx 渲染对中文表格列宽不友好 | 短标签 4~8 字已经是 docx 表格友好上限；v7 实测 `[抖动 2/3]` 6 字前缀就能稳定渲染，同长度无问题 |
| Excel 和 markdown 显示分叉，外部协作时口径混乱 | `gen_failure_tags.py` 自动生成的 README 把"英文 enum value（机读）→ 中文短标签（报告）→ 长描述（文档）"三栏对齐，一处查询全部对得上 |

## Migration Plan

不涉及数据迁移：
- `report.json` schema 不变，历史报告无需重跑
- 直接 ship 后下一次 `medeval run` 产出的 `report.md` / 飞书 docx 即生效
- 回滚：纯 revert PR 即可，无副作用

## Open Questions

无。提案阶段已敲定全部 15 条短标签词表（Decision 1）。
