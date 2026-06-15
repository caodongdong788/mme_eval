# Design

## 功能 1：维度满分展示

- `score_case` 内已有 `mmax = profile["module_max"]`（该题 profile 的四维满分）。返回 dict 增 `"dimension_max": dict(mmax)`。
- `apply_grading` 把 `bd["dimension_max"]` 写入 `r.dimension_max`。
- `CaseResult.dimension_max: dict[str, float] = {}`（默认空，兼容历史 report.json；旧 run 无此字段时前端回退为仅显示分值）。
- detail_json = `CaseResult.model_dump(mode="json")` 自动带出，无需改接口 schema。
- 前端 `CaseDetailPage` 维度分：`max != null → "{score}/{max}"`，否则 `"{score}"`。

## 功能 2：上线综合分阈值前端可配（按场景，仅新评测）

### 存储
新表 `release_threshold_config`：`profile`（唯一）、`composite_threshold`（float）、`updated_by`、`updated_at`。仅存被用户改过的 profile；无行 = 沿用 config.yaml。

### 已知 profile 与默认阈值（API 提供给前端展示）
`scoring.py` 新增纯函数 `profile_release_thresholds(scoring_cfg) -> list[{profile, max_total, default_threshold}]`：
- 已知 profile = `config.scoring.profiles` 的键 ∪ `"default"`。
- `max_total` = 该 profile `module_max`（合并 default 顶层）之和（通常 1.0）。
- `default_threshold` = pass_rule 为 `threshold` → `min_composite`；为 `perfect`/缺省 → `max_total`。

### API（`/api/config/release-thresholds`）
- `GET`：返回各 profile `{profile, label, max_total, default_threshold, override|null, effective}`。`effective = override ?? default_threshold`。
- `PUT`：body `{overrides: {profile: threshold}}`；threshold 须 `0 < x ≤ max_total`（越界 422）；profile 不在已知集 422；写入/更新或（值=默认时）删除该行。

### 注入（仅新评测）
`build_eval_job` 在 `load_config` 后调用 `apply_release_threshold_overrides(config, overrides)`（overrides 来自 DB）：
- 对每个被覆盖 profile，把其 `pass_rule` 设为 `{type: threshold, min_composite: override, gates: <该 profile 原 gates 或 {}>}`——**只改综合分阈值，保留原 gates**。
- default profile 覆盖 → 写顶层 `scoring.pass_rule`。
- 覆盖后 `config.scoring` 进入 `config_snapshot`（evaluate→build_report），故 `apply_grading` 自然生效、`fingerprint` 体现变化、diff 可区分。
- **rejudge 不自动套用**（仍以源 run 冻结 config 重判，保持"判分逻辑变化"单变量）；用户想用新阈值复算历史 run，可在重判时选对应 benchmark/judge——本期 scope=仅新评测。

### 安全约束
- 覆盖只动综合分阈值，绝不削弱 HardGate 与已有 gates（安全/合规满分生死线照旧）。
- 文档提示：红旗/对抗档建议保持满分阈值（默认 1.0），下调会降低零容错保障。

## 不变量
- 未配置任何 profile → 与今天逐字节一致（pass_rule 不动、fingerprint 不变）。
- 不改核心 schema（仅给 CaseResult 加向后兼容可选字段）、不动 judge、不动 HardGate。
