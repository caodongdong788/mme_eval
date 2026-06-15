# Proposal: 彻底移除 population / difficulty

## Why

上一轮已从内置 YAML 与 Benchmark 预览移除 `population` / `difficulty`，用户已清空历史 run/报告，现需从 schema、报告聚合、DB ORM 与 API 全链路删除，避免惰性字段继续落库。

## What Changes

- 删除 `TestCase.population` / `difficulty` 及 `Population` / `Difficulty` 枚举
- 删除 `RunReport.by_population` / `by_difficulty` 与报告/Markdown 切片
- 删除 `EvalRun` / `CaseResultRow` 对应 DB 列；`init_db` 幂等 DROP 旧列
- 删除 API `CaseRowOut` / `RunDetailOut` 对应字段
- 历史 YAML 含 `population` / `difficulty` 静默忽略（同 `case_version`）

## Impact

- Affected specs: `case-schema-and-loader`, `reporting`, `evaluation-cli`, `eval-platform-service`
- Affected code: `medeval/models.py`, `medeval/reporter/*`, `medeval/cli.py`, `server/*`, `frontend/src/api.ts`, tests
