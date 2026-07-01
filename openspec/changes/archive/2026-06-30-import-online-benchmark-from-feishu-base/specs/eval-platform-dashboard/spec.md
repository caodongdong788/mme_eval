## MODIFIED Requirements

### Requirement: benchmark 管理界面

前端 SHALL 提供 benchmark 管理页：上传 YAML 用例集、展示 benchmark 列表（含 builtin 与上传项）、查看某 benchmark 的用例清单。上传失败时 MUST 展示后端返回的校验错误。

上传弹窗 MUST 复用同一入口区分「线下 / 线上」来源：选择线下时上传标准 YAML；选择线上时，同一区域 MUST 允许用户粘贴飞书 Base URL 或拖拽 JSONL 文件，提交后由后端判断解析逻辑。线上模式的文案 MUST 明确说明「飞书 URL 或 JSONL」均可导入，且导入后会保留多轮线上对话。

#### Scenario: 上传并查看 benchmark

- **WHEN** 用户在管理页上传一个合法用例集
- **THEN** 列表中出现该 benchmark，点击可查看其用例清单

#### Scenario: 线上来源粘贴飞书 URL

- **WHEN** 用户在上传弹窗选择「线上」并填写飞书 Base URL
- **THEN** 前端 MUST 调用 benchmark 上传接口并提交 `source=online` 与 `source_url`
- **AND** 不要求用户同时选择本地文件

#### Scenario: 线上来源上传 JSONL

- **WHEN** 用户在上传弹窗选择「线上」并拖拽 JSONL 文件
- **THEN** 前端 MUST 调用同一个 benchmark 上传接口并提交 `source=online` 与文件
