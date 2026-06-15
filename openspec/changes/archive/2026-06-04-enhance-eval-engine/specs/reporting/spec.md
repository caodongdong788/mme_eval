## ADDED Requirements

### Requirement: 报告必须呈现通过率的 bootstrap 置信区间

报告层 MUST 基于各用例的 `release_passed` 计算整体通过率的 bootstrap 置信区间，并写入 `RunReport.pass_rate_ci`。计算 MUST 仅使用标准库且在给定 `seed` 下可复现；置信水平与重采样次数 MUST 取自配置（`run.stats`），默认 95% 置信、1000 次重采样。markdown 报告 MUST 在通过率旁呈现该区间并标注为"统计估计"，使读者理解小样本下的不确定性。该统计 MUST NOT 改变任何判分、否决或 `release_passed` 口径。

#### Scenario: 有样本时输出置信区间

- **WHEN** 一次评测至少有 1 条用例结果且 `run.stats.enabled=true`
- **THEN** `RunReport.pass_rate_ci` MUST 含下界与上界（0~1），且下界 ≤ 点估计 ≤ 上界

#### Scenario: 关闭统计时不产出区间

- **WHEN** `run.stats.enabled=false`
- **THEN** 报告 MUST 不计算置信区间，`pass_rate_ci` 保持为空 dict，且通过率单点值照常呈现

#### Scenario: 空结果不报错

- **WHEN** 没有任何用例结果
- **THEN** 计算 MUST 返回空区间而非抛错，报告 MUST 正常渲染
