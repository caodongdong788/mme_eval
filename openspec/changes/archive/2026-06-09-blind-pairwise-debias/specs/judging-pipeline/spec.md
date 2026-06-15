# judging-pipeline (delta)

## MODIFIED Requirements

### Requirement: 位置消偏

比较器 SHALL 通过**双盲匿名化**消除 LLM 裁判的位置与身份偏好：prompt MUST 用中性占位
「系统①（在上）/系统②（在下）」呈现两份回答，MUST NOT 向裁判暴露「基线/本次」身份；裁判
JSON 的 `winner`/`dimensions` MUST 取值 `1`/`2`/`tie`（指代位置），`reason` MUST 仅用
「系统①/系统②」指代。比较器 MUST 进行两次判定并交换「位置 ↔ 真实系统」映射（一次上=A 下=B，
另一次上=B 下=A），并 MUST 在代码侧把位置标签翻译回 A/B 语义（`reason` 文本同步翻译），
对外仍以 `A`/`B`/`tie` 表达 `winner` 与维度归属。`confidence` MUST 表达「换序后结论是否
稳健」，与最终是否平局解绑：

- 两次判定（翻译回 A/B 后）一致（无论一致判出胜负，还是一致判平）→ `swap_consistent=true`；
  此时 MUST 标 `confidence=high`（真平局也属高置信）。
- 两次判定不一致（顺序敏感）→ MUST 记 `winner=tie`、`confidence=low`、`swap_consistent=false`。
- 例外：换序一致地判出胜负、但被医疗保守规则降级为 tie 时，MUST 记 `confidence=low`。

#### Scenario: 裁判不可见真实身份

- **WHEN** 构造任一顺序的比较 prompt
- **THEN** prompt MUST 含「系统①」「系统②」中性占位，MUST NOT 含「基线」「本次」等身份措辞

#### Scenario: 位置标签翻译回语义身份

- **WHEN** pass① 上=A、裁判判位置「1」更优；pass② 上=B、裁判判位置「1」更优
- **THEN** 两次翻译回 A/B 后分别为 A、B（身份相反）→ `winner=tie`、`confidence=low`、
  `swap_consistent=false`

#### Scenario: 两次一致给出高置信胜负

- **WHEN** 两种顺序翻译回 A/B 后均判同一方更优
- **THEN** 比较器返回该方为 `winner` 且 `confidence=high`

#### Scenario: 真平局为高置信

- **WHEN** 两种顺序均判平
- **THEN** 比较器返回 `winner=tie`、`confidence=high`、`swap_consistent=true`

## ADDED Requirements

### Requirement: 顺序敏感分歧留痕

比较器 MUST 在结果中保留两次 pass 的判定留痕 `order_runs`（每项含该 pass 的上位真实身份
`top`、翻译回 A/B 的 `winner`、翻译后的 `reason`），并 MUST 随逐用例结论持久化与回显，
以便在顺序敏感用例上如实并列两次分歧，而非只展示单方面理由。

#### Scenario: 顺序敏感用例留痕两次

- **WHEN** 一道用例两次判定不一致被降级为持平
- **THEN** 其 `order_runs` MUST 含两条记录，分别反映 pass① 与 pass② 的 `winner` 与 `reason`，
  且 `reason` MUST 已翻译为 A/B 语义
