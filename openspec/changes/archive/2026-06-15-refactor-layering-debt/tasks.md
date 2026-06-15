# Tasks: refactor-layering-debt

## P0 — 共享去重 + Judge 标签

- [x] `medeval/judge_labels.py` + 单测
- [x] `GET /api/config/judge-verdict-labels` + server 单测
- [x] 前端 `useJudgeVerdictLabels` + `JudgeVerdictTable` 对齐
- [x] `medeval/reporter/token_cost.py` + characterization 单测
- [x] `server/services/config_overrides.py` + eval_job re-export
- [x] 全量 `pytest` + `medeval run --dry-run`
- [x] `graphify update .`

## P1 — Server 解耦

- [x] 拆分 `server/routers/runs/`
- [x] 拆分 `server/services/eval_*.py`

## P2 — Frontend 解耦

- [x] 拆分 `frontend/src/api/`
- [x] 大页面 hooks 化（`useRunDashboard` / `usePairwiseDetail`）

## P3 — 收尾

- [x] 目录归位（`scripts/compute_agreement.py`、`scripts/aidp_proxy.py`）
- [x] 日志补强（`eval_artifacts` / `eval_rejudge` / `langfuse_tracing`）
- [x] `AGENTS.md` aggregator 命名对照
- [x] 全量 `pytest` + `medeval run --dry-run`
- [x] `graphify update .`
- [x] `openspec archive refactor-layering-debt`
