# Proposal: 八维度与指南部分分评分

## Why

现有四模块、六项 rubric 与二值 scoring_points 无法表达 `cx-data-label` 已落地的乳腺癌陪伴八维标准，也无法让重要指南按覆盖程度获得部分分。历史 Case 与报告没有保留需求，因此直接替换比维护双轨兼容更清晰。

## What Changes

- Case YAML 统一升级为 `schema_version: "2.0"`，用 `evaluation.dimension_criteria` 与 `evaluation.guidelines` 描述本题判据。
- 固定评估医学安全、专业准确、临床追问、个性化、方案可行、共情、可执行、沟通体验 8 个维度。
- 指南项声明 `dimension` 与 `max_score`，模型返回 0～满分的整数；缺分从绑定维度扣除。
- 按医生/护士/患者三端归一到 45 分，安全维 0 时整题 0 分，输出优秀/良好/合格/不合格。
- 删除旧 Case、旧 Schema 字段、旧 Judge/Scorer 配置与旧四模块报告语义，不提供兼容分支。

## Scope

本变更 MUST 覆盖 medeval Schema、Judge、Reporter、默认配置、Case 示例和相关测试。前端视觉重做与新医学 Case 内容不在本次范围。
