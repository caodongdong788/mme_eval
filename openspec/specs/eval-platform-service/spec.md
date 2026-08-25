# Evaluation Platform Service

## Purpose

规定评测平台 API、持久化、重判与 Pairwise 服务的八维 v2 契约。服务只面向空库和当前数据模型创建结构，不执行任何旧评分字段迁移或兼容读取。

## Requirements

### Requirement: Benchmark API 必须严格校验 Case v2

平台 MUST 支持上传、读取、覆盖和删除 Benchmark；所有写入 MUST 经过同一 `TestCase` v2 校验。旧 Case MUST 返回 422，且不得写入数据库或文件。

#### Scenario: 上传合法 v2 Benchmark

- **WHEN** 文件包含合法八维和指南结构
- **THEN** API MUST 返回 201，并正确记录 Case 数量

### Requirement: 平台必须持久化新评分结构

评测完成后，平台 MUST 持久化 `medical_safety_passed`、八维原始分、指南逐项分、八维最终分、三端分、40 分总分、评级和 `release_passed`。`detail_json` MUST 无损保留 Case、trace 与 verdict。

#### Scenario: 读回 Case 明细

- **WHEN** 客户端读取已完成 run 的 Case
- **THEN** 响应 MUST 含完整八维、指南、三端与总分数据

### Requirement: Judge 模型凭据必须安全

平台 SHALL 允许选择 Judge 模型，并 MUST 把同一连接配置应用到八维与指南 Judge。API key MUST 只在运行期注入，MUST NOT 通过列表、详情或 run 配置快照明文返回。

#### Scenario: 使用已保存 Judge 模型发起评测

- **WHEN** 用户选择含 API key 的模型
- **THEN** Job MUST 收到凭据，但 run 的公开 `judge_overrides` MUST 不含 `api_key`

### Requirement: 平台必须公开统一评测标准

`GET /api/config/evaluation-standard` MUST 返回固定八维、角色端、每端满分、40 分总分、四档阈值、医学安全归零规则与指南扣分公式。

#### Scenario: 前端读取评测标准

- **WHEN** 客户端请求标准接口
- **THEN** 响应 MUST 含恰好八个维度且 `total_max_score=40`

### Requirement: 重判和预览只能覆盖 evaluation

重判、Benchmark 派生和单 Case 预览 SHALL 允许覆盖 `evaluation.dimension_criteria` 与 `evaluation.guidelines`，并 MUST 重新通过 v2 校验。冻结 trace MUST 保持不变，重判 MUST NOT 调用 bot。

#### Scenario: 指南满分被修改

- **WHEN** 合法覆盖修改某条 guideline 的 `max_score`
- **THEN** 重判 MUST 使用新满分重新评分并生成独立 run

### Requirement: Pairwise 可比性必须使用新判分尺子

Pairwise MUST 要求相同 Benchmark、相同 Case 集合、相同八维/指南 Judge fingerprints 和双方 trace 可用。系统 MUST NOT 比较或读取已删除的评分配置段。

#### Scenario: 八维 fingerprint 不同

- **WHEN** 两个 run 使用不同八维 Judge fingerprint
- **THEN** Pairwise MUST 拒绝并指出八维评分标准不同

### Requirement: 数据库必须按当前模型从空库创建

平台启动时 MUST 以当前 ORM 创建数据库表；本版本 MUST NOT 执行旧字段迁移、回填或兼容读取。

#### Scenario: 新环境启动

- **WHEN** 数据库为空
- **THEN** 服务 MUST 创建包含新评分列的完整表结构
