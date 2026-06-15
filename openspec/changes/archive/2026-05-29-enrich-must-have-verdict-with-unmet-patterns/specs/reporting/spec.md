## ADDED Requirements

### Requirement: Markdown 失败样本段必须为 unmet_patterns 渲染子列表

Markdown 报告的"失败样本 Top N"段对每条 fail verdict，若其 `unmet_patterns` 非空，MUST 在该 verdict 行下方以 2 空格缩进的子列表形式列出每条未命中的 `Pattern`，每项 MUST 标明类型（"关键词" 或 "正则"）并以反引号包裹模式内容以避免 Markdown 转义。`unmet_patterns` 为空的 verdict（HardGate / LLM / 通过的 verdict / `rule.must_not_have`）MUST 维持原有单行渲染，不出现空子列表。

主行 reason 维持 RuleJudge 给出的人话总结，子列表与 reason 之间不插入额外提示文案。子列表 MUST 使用标准 Markdown 嵌套 list 语法（`-` 加 2 空格缩进），保证飞书 docx 在 markdown 导入时正确渲染为嵌套列表。

#### 场景:OR 模式全部未命中时渲染完整子列表

- **当** 失败样本含 `rule.must_have` verdict，`unmet_patterns = [Pattern(keyword="升糖"), Pattern(keyword="粗粮"), Pattern(regex="(白粥|油条).{0,12}(不建议|不推荐)")]`
- **那么** 该 verdict 行下方必须紧跟三行子列表，依次为：
  - `  - 关键词 \`升糖\``
  - `  - 关键词 \`粗粮\``
  - `  - 正则 \`(白粥|油条).{0,12}(不建议|不推荐)\``

#### 场景:AND 模式部分未命中时只列缺失子集

- **当** 失败样本含 `rule.must_have` verdict，`unmet_patterns = [Pattern(keyword="A"), Pattern(keyword="C")]`（B 已命中已被剔除）
- **那么** 子列表必须只含 A 与 C 两条，不出现 B

#### 场景:其它 verdict 不渲染子列表

- **当** 失败样本含 `rule.must_not_have` verdict（命中禁含项，`unmet_patterns = []`）
- **那么** 仍按原格式输出单行 `- **rule.must_not_have** ✗ 命中禁含：xxx 证据：\`xxx\``，不追加任何子列表

#### 场景:正则中含 Markdown 特殊字符

- **当** unmet pattern 是 `Pattern(regex="\\d+\\s*(mg|毫克)")`
- **那么** 渲染必须形如 `  - 正则 \`\\d+\\s*(mg|毫克)\``（用反引号包裹，原样保留 `\d` `\s` `|` 等字符，飞书 docx 不会把它们解释为格式）

#### 场景:unmet_patterns 字段缺失时回退到旧渲染

- **当** 加载一份旧版 `report.json`，verdict 中无 `unmet_patterns` 字段（默认 `[]`）
- **那么** Markdown 渲染必须不抛错，输出退化为旧的单行格式（不出现空子列表）
