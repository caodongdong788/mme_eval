# Proposal: 用例 source 简化为线上/线下

## Why

原 `Source` 四值（`real_log` / `expert_crafted` / `red_team` / `public_set`）描述「命题构造方式」，与当前团队口径「线上真实流量 vs 线下构造」不对齐，且不参与判分。现统一为两值枚举，当前 71 条乳腺癌 benchmark 全部标为 `offline`（线下）。

## What Changes

- `medeval/models.py::Source` 改为 `online` / `offline`，默认 `offline`。
- `cases/breast_cancer/*.yaml` 全部 `source: offline`。
- 测试 factory、文档（`cases/README.md`、根 `README.md`）同步。
- 历史 YAML 中旧 `source` 取值加载 MUST 失败（枚举收紧，非 extra ignore）。

## Impact

- Affected specs: `case-schema-and-loader`
- Affected code: `medeval/models.py`，71 条用例 YAML，测试，文档
- 行为：判分不变；新 report 中 `case.source` 为 `offline`/`online`
