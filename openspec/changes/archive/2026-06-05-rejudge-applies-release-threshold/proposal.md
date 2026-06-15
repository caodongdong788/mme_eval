# Proposal: 重判也套用当前上线综合分阈值覆盖

## Why

上线综合分阈值覆盖此前仅作用于「新发起的评测」。但用户改完阈值后自然会用**重判**（零 bot 调用、最省）来验证 / 复算历史 run，却发现阈值没生效——重判仍按源 run 冻结口径判分，体验割裂。重判本就是「换判分口径、产出新 run」的通道，套用当前阈值在语义上完全合理。

## What Changes

- 重判（`build_rejudge_job`，含全量重判与「只重判上线失败」两条路径）MUST 在 load_config 后注入当前按 profile 的综合分上线阈值覆盖，与新评测一致；覆盖进入新 run 的 `config_snapshot` 与 `fingerprint`。
- 重判仍冻结 bot 会话留痕（零 bot 调用）；仅判分口径随当前阈值配置变化（新 run，源 run 不变）。
- 未配置任何 profile → 重判行为与今天逐字节一致。

## Impact

- Affected specs: `eval-platform-dashboard`（修订原「仅作用于新评测」表述为「新评测与重判」）。
- Affected code：`server/eval_job.py::build_rejudge_job` 增一处注入（复用 `load_release_threshold_overrides` / `apply_release_threshold_overrides`）。
- 不改判分内核、不动 HardGate 与各 profile 原有 gates。
