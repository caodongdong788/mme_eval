# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: 用例详情维度分展示满分

用例详情的「维度分」MUST 以 `当前分/满分` 格式展示每个维度（安全/合规/功能/体验），满分取该题所属评分 profile 的 `module_max`。当结果来自不含满分信息的历史 run 时，MUST 优雅回退为仅展示当前分值，不报错。

#### Scenario: 展示维度满分

- **WHEN** 打开一条用例详情且其结果含维度满分信息
- **THEN** 每个维度 MUST 显示为 `分/满分`（如对抗档 `体验 0.075/0.10`）

### Requirement: 上线综合分阈值前端按场景可配

平台 MUST 提供前端入口，按评分档（profile：default/red_flag/adversarial/knowledge/rehab）分别配置「综合分上线阈值」。配置 MUST 持久化，且 MUST 仅作用于之后发起的新评测——注入该 run 的 `config_snapshot` 并进入判分 `fingerprint`，使 diff 可区分口径变化。未配置的 profile MUST 完全沿用服务端 `config.yaml` 现状（零行为变化）。阈值覆盖 MUST 只改综合分阈值，MUST NOT 削弱该 profile 原有的安全/合规 gates 与 HardGate。阈值越界（≤0 或 > 该 profile 满分）或未知 profile MUST 返回 422。

#### Scenario: 按场景调上线阈值并对新评测生效

- **WHEN** 用户把某评分档的综合分上线阈值改为某合法值并保存，随后发起新评测
- **THEN** 新评测对该档用例的 `release_passed` MUST 按新阈值判定，且该阈值 MUST 写入新 run 的 `config_snapshot`

#### Scenario: 未配置时不改变现状

- **WHEN** 未对某 profile 设置任何阈值覆盖
- **THEN** 该 profile 的上线判定 MUST 与 `config.yaml` 原 `pass_rule` 逐字节一致

#### Scenario: 非法阈值拒绝

- **WHEN** 提交的阈值 ≤0、超过该 profile 满分，或 profile 未知
- **THEN** 系统 MUST 返回 422 且不落库
