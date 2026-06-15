# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: 判分模型配置中心

平台 MUST 提供「判分模型（LLM-as-Judge）配置」的全局 CRUD：后端 MUST 持久化 `judge_model_config`
（name 唯一、provider/model/base_url/api_version/temperature/api_key/created_by），并暴露
`GET/POST/PATCH/DELETE /api/judge-models`。配置 MUST 全局共享（所有登录用户可见可用）。
API Key MUST 落库但只写不读：读取类接口 MUST NOT 明文返回 Key，仅返回 `has_api_key` 掩码标记。
名称重复 MUST 返回 409。前端「资源」区 MUST 提供该配置页（增删改、Key 写入与掩码展示）。

#### Scenario: 配置后下拉复用且 Key 不外泄

- **WHEN** 用户在配置页保存一个带 API Key 的判分模型
- **THEN** 列表接口 MUST 只返回 `has_api_key=true` 而非明文 Key，且该模型 MUST 可在发起评测处被选用

### Requirement: 发起评测选择判分模型

发起评测 `POST /api/runs` MUST 支持 `judge_model_id`：选中时后端 MUST 据该配置构建 judge 覆盖
（连接信息 + 服务端读取的 Key 注入运行期），且 MUST NOT 把 Key 写入 run 的 `judge_overrides`；
未选时 MUST 沿用服务器 `config.yaml` 默认判分模型。发起评测页打分模型区 MUST 以下拉选择替代手填连接信息。

#### Scenario: 下拉选模型发起评测

- **WHEN** 用户在发起评测页选择某个已配置的判分模型并提交
- **THEN** 该 run MUST 用所选模型判分，且 run 的 `judge_overrides` MUST NOT 含明文 Key

## MODIFIED Requirements

### Requirement: 用例详情中文映射

用例详情页 MUST 对枚举/标识类值做中文映射展示：评分档（profile）、稳定性（stability）、维度分与扣分原因的维度
key（safety/compliance/function/experience）、Judge 列的 judge key（`hard_gate.*` / `rule.*` / `llm.*` / `scoring_point.*`）。
未知值 MUST 安全回退为原始字符串，且映射 MUST NOT 改变后端数据或判分。
此外，详情页返回操作 MUST 落到看板「用例明细」tab（而非「概览」），且看板 tab MUST 随选择记忆。

#### Scenario: 详情页中文呈现

- **WHEN** 用户打开某用例详情
- **THEN** 评分档/稳定性/维度 key/Judge key MUST 以中文呈现（未知值回退原文）

#### Scenario: 从详情返回用例列表

- **WHEN** 用户在用例详情页点击返回
- **THEN** MUST 回到该 run 看板的「用例明细」列表 tab
