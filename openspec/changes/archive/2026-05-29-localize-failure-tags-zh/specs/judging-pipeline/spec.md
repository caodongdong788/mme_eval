## ADDED Requirements

### Requirement: FailureTag 元数据必须额外携带 label_zh 短中文标签

`FailureTag` 枚举的元数据容器 `_TagMeta` MUST 在原有 `dimension` 与 `description` 之外，额外携带 `label_zh: str` 字段。该字段值 MUST 为 4~8 字的中文短词，作为面向报告读者的紧凑显示标签（区别于 `description` 的长句说明）。

`_TAG_META: dict[FailureTag, _TagMeta]` MUST 为枚举的全部成员（已 emit 与预留共 15 项）提供非空 `label_zh`。`FailureTag` MUST 暴露 `label_zh` property，等价于 `_TAG_META[self].label_zh`，与既有 `dimension` / `description` property 的访问方式保持一致。

启动期完整性自检 MUST 同时校验：
- `set(_TAG_META.keys()) == set(FailureTag)`（既有断言）
- `all(meta.label_zh for meta in _TAG_META.values())`（新增断言，避免新成员遗漏 label_zh）

`label_zh` MUST 与 `dimension` 维度对齐但更具体（例如同属 `communication` 维度的 `inquiry_incomplete` / `constraint_violation` / `empathy_miss` 各自有独立短标签，不允许重名）。

#### Scenario: 已 emit 标签的 label_zh 词表

- **WHEN** 单测读取下列已 emit 标签的 `label_zh`
- **THEN** 取值 MUST 严格等于：
  - `MISSED_RED_FLAG.label_zh == "漏报红旗"`
  - `UNDER_REFERRAL.label_zh == "转诊不足"`
  - `IMPROPER_PRESCRIPTION.label_zh == "越界处方"`
  - `OVER_DIAGNOSIS.label_zh == "越界确诊"`
  - `DISCLAIMER_MISS.label_zh == "缺免责"`
  - `INQUIRY_INCOMPLETE.label_zh == "问诊不足"`
  - `CONSTRAINT_VIOLATION.label_zh == "触发禁词"`
  - `ADAPTER_ERROR.label_zh == "调用失败"`

#### Scenario: 预留标签也必须有 label_zh

- **WHEN** 单测读取预留标签的 `label_zh`
- **THEN** 取值 MUST 严格等于：
  - `EMPATHY_MISS.label_zh == "共情不足"`
  - `POPULATION_BLIND.label_zh == "人群盲区"`
  - `DIFFERENTIAL_NARROW.label_zh == "鉴别窄"`
  - `MEDICAL_HALLUCINATION.label_zh == "医学幻觉"`
  - `OVER_REFUSAL.label_zh == "过度拒答"`
  - `DIALOG_BREAK.label_zh == "上下文断"`
  - `TOOL_MISUSE.label_zh == "工具误用"`

#### Scenario: 启动期完整性自检覆盖 label_zh

- **WHEN** `medeval/models.py` 加载时遍历 `_TAG_META`
- **THEN** 任何成员 `label_zh` 为空字符串或 None MUST 触发 `AssertionError`，错误消息 MUST 指出哪个 `FailureTag` 成员缺 `label_zh`

#### Scenario: label_zh 不与 dimension 取值冲突

- **WHEN** 单测枚举 `FailureTag` 全部成员
- **THEN** `label_zh` 全集与 `dimension` 全集 MUST 不重叠（`label_zh` 是中文短标签，`dimension` 是英文枚举键，二者语义层不同）；任何两个成员的 `label_zh` MUST 互不相同（避免飞书报告里两个不同 tag 渲染成同一个中文）

### Requirement: failure_tags 字段的字符串语义保持英文 enum value 不变

本 change 引入 `label_zh` 后，`JudgeVerdict.failure_tags` 与 `CaseResult.failure_tags` 字段的 list[str] 序列化值 MUST 仍写英文 enum value（`FailureTag.MISSED_RED_FLAG.value == "missed_red_flag"`），不得改写为 `label_zh`。`label_zh` 仅作为渲染层（markdown 报告、README 文档）的展示属性。

#### Scenario: 历史 report.json 反序列化兼容

- **WHEN** 加载本 change 落地前生成的 `report.json`，其中 `failure_tags` 为英文字符串数组
- **THEN** `RunReport.model_validate_json(...)` MUST 仍能成功，加载后的 `CaseResult.failure_tags` 形态保持英文 enum value 字符串

#### Scenario: 新版评测落盘的 report.json 仍为英文

- **WHEN** 本 change 落地后跑一次新评测，写出 `outputs/<run>/report.json`
- **THEN** JSON 中 `failure_tags` 数组与 `failure_tag_counter` dict 的 key MUST 全部是英文 enum value（如 `"missed_red_flag"`），不含 `label_zh` 中文
