# Tasks: 移除 TestCase.case_version 字段

## 1. 测试先行（TDD）
- [ ] 1.1 在 loader/models 测试中补一条：含 `case_version` key 的 YAML 用例 MUST 正常加载（extra 被忽略），且生成的 `TestCase` 实例 MUST NOT 暴露 `case_version` 属性。

## 2. 实现
- [ ] 2.1 从 `medeval/models.py::TestCase` 移除 `case_version` 字段及其注释。
- [ ] 2.2 更新 `medeval/judges/scoring_point.py::fingerprint()` docstring，去掉 `case_version` 引用。

## 3. 规格
- [ ] 3.1 `case-schema-and-loader/spec.md`：从「可审计」原则与字段清单需求中移除 `case_version`。
- [ ] 3.2 `judging-pipeline/spec.md`：从 ScoringPointJudge fingerprint 需求与指南要点库需求中移除 `case_version` 叙述。

## 4. 验证
- [ ] 4.1 `pytest` 全量绿。
- [ ] 4.2 `medeval validate`：71 条用例全部加载通过。
- [ ] 4.3 `medeval run --config config.yaml --dry-run`：主链路装配通过。
- [ ] 4.4 `graphify update .` 刷新图谱。
- [ ] 4.5 `openspec validate --strict remove-case-version-field` 通过后归档。
