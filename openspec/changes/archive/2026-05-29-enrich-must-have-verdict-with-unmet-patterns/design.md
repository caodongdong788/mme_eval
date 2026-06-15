## Context

参见 `proposal.md`。当前 `RuleJudge._check_must_have` 在 must_have 失败时只把"为什么挂"压缩成一句字符串放进 `JudgeVerdict.reason`，原始的 `Pattern` 列表（每项 `keyword` 或 `regex`）丢失。`markdown_report._failure_section` 直接拼接 `verdict.reason + verdict.evidence` 渲染失败行，没有访问 case 原始 `must_have` 的渠道。

数据流现状：

```
case.expected_behavior.must_have: list[Pattern]
        │
        ▼
RuleJudge._check_must_have
        │
        ├─ OR 全 miss   ──► reason = "全部 must_have 均未命中", evidence = []
        ├─ AND 任一 miss ──► reason = "缺失：xxx, yyy"   (字符串拼接，丢类型信息)
        └─ 通过          ──► reason = "命中：…",         evidence = [...]
        │
        ▼
JudgeVerdict (name, passed, score, reason, evidence, failure_tags)
        │
        ▼
markdown_report._failure_section  ──►  "- **rule.must_have** ✗ <reason> 证据：`<evidence>`"
```

约束：
- `report.json` 已被外部消费（飞书 docx 是其副本，未来可能有 dashboard），新字段必须**向后兼容**：旧 JSON 没有该字段也能 load。
- `RuleJudge.fingerprint` 是 diff 与判官缓存身份的一部分，**不能**因为这次扩展而改变（fingerprint 改变 = 历史报告无法 diff），所以扩展只能加在输出端，不能动 `_normalize` 源码或 `normalize` 配置。
- `Pattern` 是已有 Pydantic 模型（`models.py`，`keyword: str | None` + `regex: str | None`），可直接序列化进 `JudgeVerdict`。

## Goals / Non-Goals

**Goals:**
- 飞书 docx / 本地 markdown 报告里，`rule.must_have ✗` 行下方以子列表形式列出"期望命中但未命中"的所有模式，每条标明类型（关键词 / 正则）。
- `report.json` 的 `verdicts[*]` 包含 `unmet_patterns: list[Pattern]` 字段，让外部消费者也能拿到结构化信息。
- AND 模式（`must_have_all=true`）失败时统一用同款渲染，替代现在的 `"缺失：xxx, yyy"` 字符串拼接。
- 通过的 verdict、`must_not_have`、`hard_gate.*`、`llm.*` 的 `unmet_patterns` 始终为空，不冗余。

**Non-Goals:**
- 不动 `must_not_have` 渲染（命中已自带 evidence，未命中没必要列）。
- 不在 `transcripts.xlsx` 概览页加 verdict 详情列（xlsx 是流水，不是 judge 详情面板）。
- 不引入"模式可读注释"机制（case 作者目前没在 yaml 里写人话标签，超本次范围）。
- 不改 Rule Judge 的 fingerprint 或 `_normalize` 行为，避免破坏历史 diff。
- 不改阈值/聚合统计（这次只是可读性增强）。

## Decisions

### D1：字段命名 `unmet_patterns` 而非 `expected_patterns`

候选：
- `expected_patterns` — 不管 verdict 通过失败，永远等于 case 的 `must_have`。
- `unmet_patterns` — 只在失败时填充未命中那部分；通过时 `[]`。

选 `unmet_patterns`：
- 语义直接对应失败原因（"哪些没满足"），渲染端只需检测非空即可决定是否渲染子列表，不需要先看 verdict 是否通过。
- 减少 `report.json` 体积（通过的 verdict 不冗余存 case 数据）。
- 通过时默认空，向后兼容旧报告天然契合。

代价：消费方若想显示"完整 must_have 清单"还得回到 case yaml；但本次诉求是"看到为啥挂"，刚好被 `unmet_patterns` 覆盖。

### D2：扩展 `JudgeVerdict` 而非加 `RuleVerdict` 子类

候选：
- 加 `RuleVerdict(JudgeVerdict)` 子类只在 rule 判官上带 `unmet_patterns`。
- 直接在 `JudgeVerdict` 上加字段，默认 `[]`。

选直接扩展：
- Pydantic + JSON 序列化对所有 verdict 一视同仁，子类化反而要在 reporter 里做 isinstance 分支。
- 字段默认 `[]`，对其它判官（hard_gate、llm）零影响。
- 未来如果别的判官也想表达"未满足条件"（比如 hard_gate 列出未通过的具体门），同一字段可复用。

### D3：渲染层 markdown 子列表，缩进 2 空格

格式：
```
- **rule.must_have** ✗ 全部 must_have 均未命中（期望任一命中）
  - 关键词 `升糖`
  - 关键词 `粗粮`
  - 正则 `(白粥|油条|精制).{0,12}(不建议|不推荐|高升糖|尽量避免|减少)`
```

要点：
- 主行 reason 末尾追加 `（期望任一命中）` 或 `（缺失全部）` 作为 OR/AND 模式的提示。
- 每个 unmet pattern 一行，前缀类型词（"关键词" / "正则"），内容用反引号包裹避免 Markdown 转义（特别是正则里的 `*`、`[`、`|`）。
- 两空格缩进对齐 markdown 嵌套 list 规范，飞书 docx 渲染兼容。

被否决的方案：
- inline 拼到 reason 一行 → 长正则会非常难读，违背"读报告不必翻 yaml"的目标。
- 表格形式 → 表格在飞书 docx 嵌套到 list item 下显示不友好。

### D4：`reason` 文案区分 OR / AND

现状 OR `"全部 must_have 均未命中"` 与 AND `"缺失：xxx, yyy"` 文案分裂。改完后：
- OR 失败：`"全部 must_have 均未命中（期望任一命中）"`
- AND 失败：`"must_have 部分未命中（要求全部命中）"`，缺失的具体模式不再塞 reason，挪到 `unmet_patterns` 子列表。

理由：把"为啥挂的人话总结"留在 reason，把"哪些没命中的结构化清单"留在 `unmet_patterns`，职责清晰。

### D5：fingerprint 不变

`RuleJudge.fingerprint()` 当前覆盖 `_normalize` 源码 + `normalize` 配置开关。本次只增加 verdict 输出字段，**判定逻辑（哪些 case 该 pass / fail）完全不变**。fingerprint 维持原值意味着新旧报告可以正常 diff（同 fingerprint 默认认为判官同源）。

代价：消费方若仅看 fingerprint 无法察觉 verdict 数据契约扩展。可接受，因为 `unmet_patterns` 是**单调扩展**（旧消费方忽略该字段没影响，新消费方默认 `[]`）。

## Risks / Trade-offs

- **Risk：长正则污染报告外观**。case 里最长正则约 50 字符，主流屏幕一行可显，且子列表本就独立成行，可读性可控。**Mitigation：** 不引入截断逻辑；如未来真的出现 200+ 字符正则再加 `_TRUNCATE_THRESHOLD` 配置。

- **Risk：旧 `report.json` 没有 `unmet_patterns` 字段，`diff.py` / `aggregator.py` 加载时报错**。**Mitigation：** Pydantic 字段默认 `Field(default_factory=list)` 已覆盖；额外加一个加载旧 JSON 的单测做回归保护。

- **Risk：渲染端把 `unmet_patterns` 误用到通过 verdict 上**（比如未来重构时不小心把新字段往所有 verdict 灌）。**Mitigation：** 渲染端逻辑写死"非空才渲染子列表"，并加单测：通过的 verdict 即使误填了 `unmet_patterns` 也不会出现在失败样本段（因为通过的 case 根本不会进 `_failure_section`）。

- **Risk：`Pattern` 模型未来再加字段**（如 `description` 人话标签），渲染端硬编码"关键词/正则"二选一会漏渲染。**Mitigation：** 渲染逻辑用 `if p.regex` / `elif p.keyword` 分支，未知类型 fallback 到 `repr(p)`，保证不崩；同时记入"Open Questions"。

- **Trade-off：`report.json` 体积小幅增大**。失败 case 平均 2-3 个 pattern，每个 ~30 字符，单 case 增量 < 200 字节。40 case 全失败极端场景增量 < 8KB，可忽略。

## Migration Plan

无 schema 迁移。
- 新代码部署后，老 `report.json` 加载默认 `unmet_patterns=[]`，渲染端逻辑回退到旧行为（不渲染子列表）。
- 新跑的评测 `report.json` 自动包含新字段，飞书 docx 重发即同步。
- 不需要重新跑历史评测来"补字段"。

回滚：直接 revert 代码即可，新版 `report.json` 在老代码下也能加载（Pydantic 默认忽略未知字段）。

## Open Questions

- 未来如果给 `Pattern` 加 `label` / `description` 人话标签字段，渲染端要不要优先显示标签而不是裸 keyword/regex？— 超本次范围，先记录。
- 若以后做 dashboard，`unmet_patterns` 是否需要再细分"是 OR 全 miss 还是 AND 部分 miss"？— 现在 reason 里有人话提示，结构化字段里没有"模式"维度。是否要加 `verdict.must_have_mode: "or"|"and"`？暂不加，等真有消费方再说。
