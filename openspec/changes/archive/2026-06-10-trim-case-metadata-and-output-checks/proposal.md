# Proposal: 精简用例元数据并规范字段顺序

## Why

`population` / `difficulty` 仅用于分组展示，71 条内置用例取值高度同质（`adult` / `medium`），YAML 与 Benchmark 预览列无实际区分度。`score_profile` 当前写在 case 末尾，与 `level` 同属路由判分元数据，应相邻便于编写。`output_checks` 已在 schema 定义但内置用例均未显式写出，不利于作者发现该能力。

## What Changes

- 从 `cases/breast_cancer/*.yaml` 全部 71 条移除 `population`、`difficulty`；`score_profile` 移至 `level` 之后；`expected_behavior` 下显式添加 `output_checks: []`。
- Benchmark 预览 API `CaseBrief` 与前端 Benchmarks 用例表移除 `population` / `difficulty` 展示。
- 更新 `cases/README.md` 字段说明与示例。
- `TestCase` schema 保留 `population` / `difficulty` 默认值以兼容旧上传 YAML；新内置集不再写入。

## Impact

- Affected specs: `case-schema-and-loader`
- Affected code: `cases/breast_cancer/*.yaml`、`server/schemas.py`、`server/routers/benchmarks.py`、`frontend/src/pages/BenchmarksPage.tsx`、`frontend/src/api.ts`、`cases/README.md`
