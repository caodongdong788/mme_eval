# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: 用例明细 Langfuse 链路入口

平台「用例明细」MUST 为每条用例提供「追踪链路」入口：当该用例存在 Langfuse trace 深链（`langfuse_trace_url`）时，前端 MUST 展示一个可点击入口，在新标签页打开该用例在自托管 Langfuse 的完整流程追踪；当深链为空（追踪关闭/未配置/旧 run）时，入口 MUST 隐藏。后端用例明细接口 MUST 暴露每条用例的 `langfuse_trace_url`（来自报告中代表 trace），且 MUST NOT 因该字段缺失而报错（旧 run 安全回退为空）。该入口 MUST NOT 改变任何判分数据或评分。

#### Scenario: 有链路时可一键跳转

- **WHEN** 某条用例的报告含非空 `langfuse_trace_url`
- **THEN** 用例明细 MUST 展示「追踪链路」入口，点击 MUST 在新标签页打开该 trace

#### Scenario: 无链路时隐藏入口

- **WHEN** 某条用例无 `langfuse_trace_url`（追踪关闭/未配置/旧 run）
- **THEN** 用例明细 MUST NOT 展示该入口，且页面 MUST 正常渲染
