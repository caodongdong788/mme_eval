# Proposal: 用例详情维度满分展示 + 上线判定综合分阈值前端可配

## Why

1. **维度分看不出满分**：用例详情「维度分」只显示绝对分（如 体验 0.075），看不出该维度满分是多少（对抗档体验满分 0.10）。用户无法一眼判断"扣了多少 / 离满分多远"，也难理解为何综合分 0.97 仍上线失败。
2. **上线判定阈值写死在 config.yaml**：不同场景（profile）的综合分上线阈值（`perfect`=满分 / `threshold`=`min_composite`）只能改服务端 `config.yaml`，非工程同学无法按业务诉求自助调整（如把对抗档放宽到 0.95）。

## What Changes

1. **维度分展示满分**：用例详情每个维度分 MUST 以 `当前分/满分` 格式展示（如 `体验 0.075/0.10`），满分取该题 profile 的 `module_max`。
2. **上线综合分阈值前端可配（按场景）**：新增前端配置入口，MUST 支持按评分档（profile：default/red_flag/adversarial/knowledge/rehab）分别设置「综合分上线阈值」。配置持久化，MUST 仅作用于**之后发起的新评测**（注入该 run 的 `config_snapshot`，进入 `fingerprint` 让 diff 可解释）；未配置的 profile MUST 完全沿用 `config.yaml` 现状（零行为变化）。覆盖只改综合分阈值，MUST 保留该 profile 原有的安全/合规 gates 生死线。

## Impact

- Affected specs: `eval-platform-dashboard`。
- Affected code：
  - `medeval/models.py`：`CaseResult` 加 `dimension_max`（默认空 dict，兼容旧 report）。
  - `medeval/reporter/scoring.py`：`score_case` 返回 `dimension_max`，`apply_grading` 写入；新增按 profile 解析「有效上线阈值/满分」的纯函数供 API 复用。
  - `server/models_db.py`：新增 `ReleaseThresholdConfig`（profile → composite_threshold）。
  - `server/routers/config.py`：`GET/PUT /api/config/release-thresholds`。
  - `server/eval_job.py`：`build_eval_job` 在 load_config 后注入上线阈值覆盖（仅新评测；rejudge 不自动套用，保持单变量）。
  - `frontend/src/pages/CaseDetailPage.tsx`：维度分渲染 `分/满分`。
  - 新增前端「上线判定阈值」配置页 / 区块 + `frontend/src/api.ts` 类型与接口。
- 不改 `TestCase` / `BaseJudge` / `FailureTag`；不动 HardGate；安全/合规 gates 不被削弱。
