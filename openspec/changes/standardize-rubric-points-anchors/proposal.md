# Proposal: standardize-rubric-points-anchors

## Why

现有 18 题 `rubric.points` 使用检查项清单写法，LLM judge 无法从 prompt 直接对照 0～max 整数分档。统一为 `"N 分=…"` 显式分档，提升判分可解释性与复现性。

## What

- 将 `agent.yaml`、`multi_turn.yaml`、`adversarial.yaml` 中全部 `rubric.*.points` 改为 `0 分`…`max 分` 分档句式。
- `cases/README.md` 中「不推荐」对比示例改为注明全库已统一显式分档。

## Scope

- **In**: `cases/breast_cancer/{agent,multi_turn,adversarial}.yaml`、`cases/README.md`
- **Out**: 判分代码、无 `rubric.points` 的用例、 `scoring_points`

## Success

- 全库 `rubric.points` 条目均以 `"N 分="` 开头，且 N 覆盖 0～max。
- `medeval list-cases` / 相关 loader 测试通过。
