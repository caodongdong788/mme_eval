# eval-platform-dashboard Specification (delta)

## MODIFIED Requirements

### Requirement: 上线综合分阈值前端按场景可配

平台 MUST 提供前端入口，按评分档（profile：default/red_flag/adversarial/knowledge/rehab）分别配置「综合分上线阈值」。配置 MUST 持久化，且 MUST 作用于之后发起的**新评测与重判**——注入该 run 的 `config_snapshot` 并进入判分 `fingerprint`，使 diff 可区分口径变化。重判仍冻结 bot 会话留痕（零 bot 调用），仅判分口径随当前阈值配置变化。未配置的 profile MUST 完全沿用服务端 `config.yaml` 现状（零行为变化）。阈值覆盖 MUST 只改综合分阈值，MUST NOT 削弱该 profile 原有的安全/合规 gates 与 HardGate。阈值越界（≤0 或 > 该 profile 满分）或未知 profile MUST 返回 422。

#### Scenario: 按场景调上线阈值并对新评测生效

- **WHEN** 用户把某评分档的综合分上线阈值改为某合法值并保存，随后发起新评测
- **THEN** 新评测对该档用例的 `release_passed` MUST 按新阈值判定，且该阈值 MUST 写入新 run 的 `config_snapshot`

#### Scenario: 调上线阈值后重判历史 run 生效

- **WHEN** 用户把某评分档阈值改为更严格的值并保存，随后对一历史 run 发起重判
- **THEN** 重判产出的新 run 对该档用例的 `release_passed` MUST 按新阈值判定（原 0.80 通过的知识档用例在阈值升到 0.90 后 MUST 失败），且新阈值 MUST 写入新 run 的 `config_snapshot`

#### Scenario: 未配置时不改变现状

- **WHEN** 未对某 profile 设置任何阈值覆盖
- **THEN** 该 profile 在新评测与重判中的上线判定 MUST 与 `config.yaml` 原 `pass_rule` 逐字节一致

#### Scenario: 非法阈值拒绝

- **WHEN** 提交的阈值 ≤0、超过该 profile 满分，或 profile 未知
- **THEN** 系统 MUST 返回 422 且不落库
