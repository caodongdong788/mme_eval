# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: 看板评测在线改名

看板 MUST 支持对当前 run 评测名称的在线编辑：双击名称进入编辑态，失焦或回车时自动保存。保存 MUST 经后端
`PATCH /api/runs/{run_id}` 校验：空白名称 MUST 拒绝（422）；与其它 run 重名 MUST 拒绝（409 并提示）；run 不存在
MUST 返回 404；名称未变化（与自身相同）MUST 允许。改名只更新 `EvalRun.name`，MUST NOT 影响判分或产物。

#### Scenario: 双击改名并自动保存

- **WHEN** 用户双击看板评测名称、改为一个未被占用的新名并失焦
- **THEN** 前端 MUST 调用改名端点保存成功并就地更新标题

#### Scenario: 重名被拒

- **WHEN** 用户把名称改为与另一个已有 run 相同
- **THEN** 后端 MUST 返回 409，前端 MUST 提示重名且不更新标题

## MODIFIED Requirements

### Requirement: 单次评测看板

前端 SHALL 为单次 run 呈现聚合看板：核心指标卡（综合分/通过率/硬门槛失败/稳定性/待审）、四模块平均分、
分层级的**用例数量与通过率**（组合图）、失败标签分布（饼图）、延迟/成本，以及与上一次 run 的 diff。看板内容
MUST 以「概览 / 用例明细」标签页组织（待审信息由概览 KPI 与用例明细筛选承载，不单设人工审核标签页）。
名称下方 meta MUST 精简为 judge 模型与 N（repeat 次数）两项。

#### Scenario: 查看单次评测看板

- **WHEN** 用户打开某次 run 的看板
- **THEN** 页面 MUST 在「概览」展示上述聚合指标与图表（分层级图含数量+通过率、失败标签为饼图），
  在「用例明细」展示可筛选的用例结果表，数据来源于数据库

#### Scenario: 分层级图同时呈现数量与通过率

- **WHEN** 用户查看「分层级通过率」图
- **THEN** 图表 MUST 同时呈现每个 level 的用例数量与通过率
