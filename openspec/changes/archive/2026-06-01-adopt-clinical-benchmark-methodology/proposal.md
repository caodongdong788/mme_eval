## Why

外部《乳腺癌专项 AI Chatbot 评测用例集》（人审为核心的临床方案）暴露了我们自动化框架的几处短板，值得吸收其临床严谨性，同时保留我们「可持续自动回归」的优势：

1. **评分权重一刀切**：不论题型都用固定四模块（安全0.30/合规0.15/功能0.35/体验0.20）。但红旗/对抗题该重安全、知识题该重指南匹配、康复题该重体验——同权重不合理。
2. **合格口径过严且单一**：「非满分即失败」对知识科普题过苛；外部方案的「80 分 + 维度得分率 gate」更分级、更贴评审直觉。
3. **缺结构化指南要点库**：外部每题都锚定 ASCO/NCCN/CACA + 版本 + 标准答案要点；我们只有一句 `notes`，指南匹配 judge 缺弹药。
4. **对抗性覆盖零散**：外部 D1–D10 systematically 覆盖虚假信息/危机沟通/非科学方案/前沿边界/低俗过滤/上下文矛盾/偏方/预期管理/质疑/药物预防，我们 `_core_safety` 不成体系（缺自相矛盾、危机沟通等探针）。
5. **病程覆盖无配额**：外部按预防筛查/症状识别/病理解读/治疗方案/康复护理/随访管理 6 类 × 难度配额，我们只有 L1–L4。

定位：**外部方案 = 临床金标准内容源 + 周期性人审校准；我们 = 持续自动回归引擎。** 本变更把外部的临床内容「编译」进我们的自动判官，并让评分模型按题型自适应。

## What Changes

- **类别自适应评分 profile（阶段1）**：评分模型从固定四模块改为 config 驱动的 `scoring.profiles` + `profile_match`（按 tags/level/红旗/多轮解析类别 → 选权重 + 阈值 + 合格规则）。默认 profile 与现状完全一致（向后兼容）。
- **分级合格规则（阶段1）**：每个 profile 可选 `pass_rule`：`perfect`（非满分即失败，红旗/对抗沿用）或 `threshold`（综合分 ≥ 阈值 + 维度 gate，知识/康复类采用）。
- **指南要点库（阶段2）**：把外部「标准答案依据」展开成机判 `scoring_points`（带 `guideline` 锚点），喂 ScoringPointJudge + 指南匹配率；先做 2–3 道样板验证。
- **对抗性套件 D1–D10（阶段3）**：新增 `cases/adversarial/` 类别，safety 重权 profile，补自相矛盾(D6)/危机沟通(D2)等新探针。
- **全量内容迁移（阶段4）**：30 单轮 + 8 多轮落 `cases/`，按病程 6 类 taxonomy 打 tag，对齐外部覆盖矩阵。
- **人审校准 + 指南版本化（阶段5，轻量）**：外部专家打分表作周期性校准集（算与自动判官一致性），指南版本接入 fingerprint/changelog 治理。

## Capabilities

### Modified Capabilities
- `reporting`: 评分从固定四模块改为类别自适应 profile（权重 + 阈值 + 合格规则可按题型配置）；`overall_passed` 口径由 profile 的 `pass_rule` 决定（默认 `perfect` 保持非满分即失败）。
- `judging-pipeline`: 明确 ScoringPoint/指南匹配率作为「指南要点库」的判分载体（要点带 `guideline` 锚点）。
- `breast-cancer-case-suite`: 新增病程 6 类覆盖矩阵 + 对抗性 D1–D10 taxonomy + 多轮场景背景卡结构；标准答案依据落为 `scoring_points`。

## Impact

- 代码：`medeval/reporter/scoring.py`（profile 解析 + 阈值/合格规则）、`config.yaml`（`scoring.profiles` / `profile_match`）、`cases/**`（新增/迁移用例）。
- 兼容性：不配 `profiles` 时行为与现状完全一致；历史 `report.json` 仍可加载。`overall_passed` 在采用 `threshold` 的类别上语义变化，相应放宽 CI 门槛由 `thresholds` 配置控制。
- 分阶段落地，每阶段独立可测、可回归；收尾统一补 spec delta + 全量测试 + 归档。
