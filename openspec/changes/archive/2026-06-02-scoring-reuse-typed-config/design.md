# Design — scoring 复用 typed schema 解析

## 边界解析（唯一解析入口）

```python
from ..config import ScoringCfg, ProfileCfg, ThresholdRule

def _as_scoring_cfg(scoring_cfg) -> ScoringCfg:
    if isinstance(scoring_cfg, ScoringCfg):
        return scoring_cfg
    return ScoringCfg.model_validate(scoring_cfg or {})
```

`apply_grading` 收到的永远是 `config_snapshot["scoring"]`（= dump 后的 ScoringCfg dict）→ `model_validate` 幂等回灌。测试传的手搓 dict 也都是合法 ScoringCfg（profiles/profile_match/pass_rule 三写法均在 schema 内）。

## pass_rule：复用 typed，删 `_normalize_pass_rule`

`ScoringCfg.pass_rule` / `ProfileCfg.pass_rule` 已是 `None | Literal["perfect","threshold"] | ThresholdRule`。用一个轻量 typed→归一 dict 适配，产出 `resolve_profile` 既有的归一 dict（保证 `prof["pass_rule"]["type"]` 等公共契约不破）：

```python
def _pass_rule_to_dict(pr) -> dict:
    if pr is None:
        return {"type": DEFAULT_PASS_RULE}
    if isinstance(pr, str):                 # "perfect" | "threshold"
        return {"type": pr}
    # ThresholdRule
    return {"type": PASS_THRESHOLD, "min_composite": pr.min_composite, "gates": dict(pr.gates)}
```

## resolve_profile / _when_matches 读 typed

```python
def _when_matches(when: WhenCfg, case) -> bool:
    if when.tags_any and set(case.tags or []) & set(when.tags_any): return True
    if when.level_any and case.level.value in when.level_any: return True
    if when.scenario_any and case.scenario in when.scenario_any: return True
    if when.red_flag and case.hard_gates.red_flag_triage.value != "none": return True
    if when.multi_turn and _user_turn_count(case) >= 2: return True
    return False

def resolve_profile(case, scoring_cfg=None) -> dict:   # 签名/返回 shape 不变
    scfg = _as_scoring_cfg(scoring_cfg)
    base_max = {**DEFAULT_MODULE_MAX, **scfg.module_max}
    base_step = scfg.function_deduction if scfg.function_deduction is not None else DEFAULT_FUNCTION_DEDUCTION
    base_thresholds = {**DEFAULT_GRADE_THRESHOLDS, **scfg.grade_thresholds}
    default_profile = {... "pass_rule": _pass_rule_to_dict(scfg.pass_rule)}
    matched = next((r.profile for r in scfg.profile_match if _when_matches(r.when, case)), None)
    if not matched or matched not in scfg.profiles:
        return default_profile
    p: ProfileCfg = scfg.profiles[matched]
    return {
        "name": matched,
        "module_max": {**base_max, **(p.module_max or {})},
        "function_deduction": p.function_deduction if p.function_deduction is not None else base_step,
        "grade_thresholds": {**base_thresholds, **(p.grade_thresholds or {})},
        "pass_rule": _pass_rule_to_dict(p.pass_rule),
    }
```

`_evaluate_pass` / `score_case` / `apply_grading` / `grading_summary` / `grade_of` **不动**（仍消费归一 dict）。

## 行为对拍锚点（必须逐位一致）

- `_SCORING_CFG`（test_category_profiles）下各 profile 解析、`pass_rule.type`、threshold 的 min_composite/gates。
- pass_rule 缺省 → perfect；str → 原样；dict/ThresholdRule → threshold + 字段。
- 默认值合并：module_max / function_deduction / grade_thresholds 的 default→base→profile 覆盖顺序不变。
- `apply_grading` 写入的 dimension_scores / composite_score / grade / release_passed 与重构前一致。

## 风险与缓解

- 最敏感模块（决定 headline 评级与通过失败）。缓解：公共签名/返回 shape 全不变；改动局限在 `resolve_profile`/`_when_matches`/新增两个私有 helper；删 `_normalize_pass_rule`。靠现有 `test_category_profiles` / `test_weighted_grading` / `test_clinical_benchmark_migration` 全绿 + 新增等价测试对拍。
- `ScoringCfg` 比旧 dict-walk 更严（如 threshold 缺 min_composite 会被拒）——但 config 加载期本就用同一 schema，真实配置不可能出现；测试夹具均合法。新增一条测试明确这层 fail-fast。

## 测试（TDD）

- snapshot dict（dump 后的 ScoringCfg）→ `resolve_profile` 结果与直接传等价 dict 一致。
- pass_rule 三写法（缺省/str/dict）归一为同样的 `{"type":...}`。
- 用 `_SCORING_CFG` 跑 `score_case`/`apply_grading`，断言与重构前的维度分/评级/release_passed 一致（沿用现有断言）。
- 全量 pytest + verify-heuristics + 真实 config `--dry-run`。
