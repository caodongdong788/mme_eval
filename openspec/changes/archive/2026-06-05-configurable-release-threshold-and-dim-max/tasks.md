# Tasks

## 功能 1：维度满分展示
- [x] 1.1 `medeval/models.py`：`CaseResult.dimension_max: dict[str, float] = {}`
- [x] 1.2 `medeval/reporter/scoring.py`：`score_case` 返回 `dimension_max`；`apply_grading` 写入
- [x] 1.3 测试：apply_grading 后 `dimension_max` = 该题 profile module_max（对抗档体验 0.10 等）
- [x] 1.4 前端 `CaseDetailPage`：维度分渲染 `分/满分`（无 max 回退仅分值）

## 功能 2：上线综合分阈值前端可配
- [x] 2.1 `medeval/reporter/scoring.py`：`profile_release_thresholds(scoring_cfg)` 纯函数
- [x] 2.2 `server/models_db.py`：`ReleaseThresholdConfig` 表
- [x] 2.3 `server/eval_job.py`：`apply_release_threshold_overrides(config, overrides)` + build_eval_job 注入（仅新评测）
- [x] 2.4 `server/routers/config.py`：`GET/PUT /api/config/release-thresholds`（越界/未知 profile 422）
- [x] 2.5 测试：GET 返回默认/有效阈值；PUT 校验越界；注入后 config.scoring pass_rule 被改且保留 gates；未配置零行为变化
- [x] 2.6 前端：上线判定阈值配置页（按场景编辑综合分阈值，显示满分上限）+ `api.ts`

## 验证 / 收尾
- [x] 3.1 `pytest` 全量绿（535 passed）
- [x] 3.2 前端 tsc + vite build
- [x] 3.3 `medeval run --config config.yaml --dry-run`
- [x] 3.4 `graphify update .`
- [ ] 3.5 `openspec validate --strict` 后 `openspec archive`；同步 README/AGENTS/server README
