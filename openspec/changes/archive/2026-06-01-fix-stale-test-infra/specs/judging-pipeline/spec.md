## ADDED Requirements

### Requirement: README 失败归因标签段必须保留 AUTO-GENERATED 标记块并经单测守门

`README.md` 的失败归因标签段 MUST 由 `medeval.docs.gen_failure_tags` 机器生成，并 MUST 保留 `<!-- AUTO-GENERATED:failure-tags-start -->` 与 `<!-- AUTO-GENERATED:failure-tags-end -->` 标记块，使生成器可机器定位并整段重写。该段 MUST NOT 被手工编辑。任何对 `FailureTag` 枚举的新增/删除/重命名 MUST 重跑 `python -m medeval.docs.gen_failure_tags --write` 同步 README。该契约 MUST 由单测 `tests/test_failure_tags.py::test_readme_in_sync_with_enum` 守门（调用 `gen_failure_tags.check()`），本仓库当前非 git 仓库，pytest 即真正的防漂移闸。

#### Scenario: 缺失标记块时单测失败

- **WHEN** README 失败归因标签段缺少 `AUTO-GENERATED` 标记块（如被手工改写删除标记）
- **THEN** `gen_failure_tags.check(README)` MUST 返回非 0，`test_readme_in_sync_with_enum` MUST 失败，提示运行 `--write` 修复

#### Scenario: 枚举与 README 一致时单测通过

- **WHEN** README 含标记块且块内容与 `render()` 输出一致
- **THEN** `gen_failure_tags.check(README)` MUST 返回 0，`test_readme_in_sync_with_enum` MUST 通过
