## Why

当前每次评测会产出 4 类产物：`report.html` / `report.md` / `report.json` / 飞书文档（可选）。实际评审者的工作流是：

- 先看飞书文档做"过没过 / 哪类失败"的高层判断
- 偶尔本地翻 markdown 复盘
- HTML 几乎不打开（与 markdown 信息重复，多一份维护负担）
- JSON 完全是机器消费（diff、再处理）

也就是说：HTML 是冗余产物、JSON 是基础设施而非"用户面输出"。当前 `reporter.formats: ["html","markdown","json"]` 把这三者并列暴露给用户，让"我这次跑应该看哪份"成为决策负担。

`reporting/spec.md` 第 9 行甚至把"三态输出"写成了硬约束，但现实是评审完全不需要 HTML。

## What Changes

- 默认 `reporter.formats: ["markdown"]`（只暴露 markdown 作为人类可读产物）
- 默认 `reporter.lark.enabled: true`（飞书自动发布从 opt-in 变成 opt-out，与"评审默认看飞书"实际工作流对齐）
- JSON 仍**永远写盘**到 `outputs/<run>/report.json`（diff_runs / regression 追踪 / 任何下游脚本都需要它），但**不再暴露在 `formats` 列表里**——它是基础设施，不是用户面"格式"
- HTML 完全不再生成（默认 / 显式都不行）；删除 `medeval/reporter/html_report.py`、`templates/report.html.j2`、相关测试与文档引用
- 修改 `reporting/spec.md` 第 9 行的"三态输出"约束为"双态输出（Markdown 人类面 + JSON 数据后端），HTML 已废弃"
- 修改 `reporting/spec.md` 中"系统必须输出 HTML 报告以提供本地完整视图"整条需求为 REMOVED

## Capabilities

### Modified Capabilities

- `reporting`：删除 HTML 输出需求；JSON 由"格式之一"降级为"内部数据后端，永远写但不显示在 `formats` 中"；Markdown 成为唯一面向人的输出；飞书发布由可选变成默认开启。

## Impact

**受影响代码**

- `medeval/reporter/html_report.py` —— 删除
- `medeval/reporter/__init__.py` —— 删除 `write_html` 暴露
- `medeval/cli.py` —— 删除 HTML 渲染分支；JSON 写盘移出 `if "json" in formats` 守卫，永远写；formats 默认值改 `["markdown"]`；`reporter.lark.enabled` 默认 `true`
- `medeval/templates/report.html.j2` —— 删除
- `tests/` 中如有 HTML 渲染测试 —— 删除或重写为 markdown 测试
- README / docs 中 HTML 相关示例 —— 清理
- `openspec/specs/reporting/spec.md` —— 修改"三态输出"约束、删除 HTML 需求

**不受影响**

- `report.json` / `report.md` 内容不变
- `diff_runs` 行为不变（仍读 JSON）
- 飞书发布逻辑不变（`publish_to_lark` 接口不动），只是默认开
- Markdown 格式不变，与 `add-transcript-excel-output` 后续 change 兼容

**版本对比影响**

- 不影响 fingerprint
- 历史 HTML 报告依然存在（不删除已生成的 outputs/）；新跑不再生成

**Breaking change 风险**

- 用户若依赖某个 CI workflow 上传 `report.html` 到 artifact storage —— 会断。需要在 release note 强调 + grep 自查
- `reporter.formats: ["html"]` 显式配置会在新版报错（应给清晰提示而非默默忽略）
