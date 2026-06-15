# eval-platform-dashboard Specification (delta)

## REMOVED Requirements

### Requirement: 重判弹框可调判分口径与模型

**Reason**: 四模块满分权重为 profile 自适应（每条 case 按 profile 解析权重），弹框只能改顶层
（default + 兜底基线），对已被 profile 整组覆盖的题型不生效、语义割裂，故移除权重/阈值编辑。

## ADDED Requirements

### Requirement: 重判弹框可换 judge 模型

看板的「重判」入口 SHALL 提供一个弹框，允许用户在重判前可选填新的 judge 模型
（provider/model/base_url/api_key），提交后以该覆盖发起重判并跳转到新 run。弹框 MUST 提示
该改动仅作用于本次重判、不改服务器配置，且 MUST NOT 提供四模块权重/阈值的编辑。

#### Scenario: 从弹框换模型发起重判

- **WHEN** 用户在重判弹框里填了新的 judge 模型并提交
- **THEN** 前端 MUST 携带该 judge 覆盖调用重判 API，并在新 run 创建后跳转到其看板
