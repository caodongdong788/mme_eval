# Proposal: 用 score_profile 取代 tags

## Why

`tags` 自由字符串列表混用「评分 profile 路由」与「描述/过滤」，作者难以维护。评分权重应显式声明：每条用例单选 `score_profile`（default / red_flag / adversarial / knowledge / rehab），删除 `tags` 字段。

## What Changes

- `TestCase` 新增 `score_profile: ScoreProfile` 枚举，默认 `default`；YAML 若误写为列表则只取第一个。
- 删除 `TestCase.tags`；`resolve_profile()` 直接读 `case.score_profile`，移除 `config.yaml` 的 `profile_match` 推断。
- `config.cases.tags` → `score_profiles` 过滤；CLI `--tags` → `--score-profile`。
- 71 条用例按原 profile_match 规则迁移 `score_profile` 并删除 `tags`。
- Benchmark / ingest / 文档同步。

## Impact

- specs: `case-schema-and-loader`, `reporting`
- 判分行为不变（profile 名称与权重映射不变，仅声明方式改变）
