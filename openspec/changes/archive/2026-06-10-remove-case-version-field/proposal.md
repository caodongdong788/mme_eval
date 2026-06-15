# Proposal: 移除 TestCase.case_version 字段

## Why

`TestCase.case_version`（默认 `"v1"`）原设计为「用例内容版本锚点」，与 judge `fingerprint` 配对，用来在 diff 中区分「用例内容变了」与「bot 表现变了」。但该机制从未落地：

- 全仓库无任何代码读取 `.case_version`（判分、diff、报告、平台、测试均不消费），`judges/scoring_point.py` 仅在 docstring 里提了一句「由 case_version 追踪」。
- 所有用例 YAML（`cases/breast_cancer/*.yaml`）根本没写该字段，全部依赖 schema 默认值 `"v1"`；没有任何「改用例就 bump 版本」的流程或工具。

即它是一段**惰性元数据**——序列化进 `report.json` 但永远是 `"v1"`，不产生任何信息量。保留它只会让 schema 与报告产物多一个无意义字段。本变更将其从 schema 彻底移除，简化用例契约与报告形状。

## What Changes

- 从 `medeval/models.py` 的 `TestCase` 移除 `case_version` 字段。
- 更新 `medeval/judges/scoring_point.py::fingerprint()` docstring，去掉对 `case_version` 的引用（改为说明「得分点属用例数据，不纳入 fingerprint」）。
- 更新 `case-schema-and-loader` / `judging-pipeline` 两份 spec：从字段清单、可审计性原则、得分点版本追踪叙述中移除 `case_version`。
- 兼容性：`TestCase` 未设 `extra="forbid"`（Pydantic v2 默认 `extra="ignore"`），历史上传 benchmark / 旧 YAML 中残留的 `case_version` key 会被静默忽略，不会加载报错；新产 `report.json` 不再含该字段，旧报告不受影响。

## Impact

- Affected specs: `case-schema-and-loader`、`judging-pipeline`
- Affected code: `medeval/models.py`、`medeval/judges/scoring_point.py`
- 行为影响：无（删除惰性字段）；新报告 JSON 形状去掉一个恒为 `"v1"` 的键。
