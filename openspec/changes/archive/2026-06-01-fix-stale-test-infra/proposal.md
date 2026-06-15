## Why

全量测试套件存在 4 个长期失败用例，且与最近的功能开发无关——它们是**历史基线漂移**，让 `pytest` 无法转绿、掩盖真实回归：

1. `tests/test_report_formats_default.py` 3 个 e2e 用例的 `_write_minimal_config` 硬编码了**早已删除的 `cases/L1_medical_knowledge` 目录**（乳腺癌套件迁移后该路径不存在）。结果：加载 0 条用例 → `medeval run` 不产出 `report.md` → 三个断言全挂。这是测试 fixture 与可变用例库耦合导致的脆性，与被测行为无关。
2. `tests/test_failure_tags.py::test_readme_in_sync_with_enum` 失败，根因是 `README.md` 的失败归因标签段**丢失了 `<!-- AUTO-GENERATED:failure-tags-start/end -->` 标记块**（该段被改成手工维护、保留了"请勿手动编辑"提示却删掉了机器可定位的标记）。`gen_failure_tags.check()` 找不到标记块即判不同步。这违反了既有需求「README 必须由枚举自动生成对应段落」。

两类问题都不改变产品行为：修复即**恢复对既有 spec 的符合**（report.json/md 无条件写盘；FailureTag 词表为 README 单一信任源），并让回归测试不再依赖会移动的用例目录。

## What Changes

- **测试解耦**：重构 `_write_minimal_config`，在 `tmp_path` 内自带一个最小合法用例 YAML 并指向它，彻底脱离 `cases/` 仓库目录布局；3 个 e2e 用例恢复通过。
- **README 标记恢复**：用 `python -m medeval.docs.gen_failure_tags --write` 重新注入 `AUTO-GENERATED` 标记块并按 `FailureTag` 词表重生成表格；同步测试恢复通过。
- **spec 校准**：把「README 必须由枚举自动生成」场景的执行契约从「CI 中与 git diff 为空」修正为符合实际的「`test_readme_in_sync_with_enum` 单测调用 `gen_failure_tags.check()`，且 README MUST 保留 `AUTO-GENERATED` 标记块」（本仓库当前非 git 仓库，真正的守门是 pytest）。

## Capabilities

### Modified Capabilities
- `judging-pipeline`: 校准「FailureTag 枚举元数据」需求中 README 自动生成场景的执行契约（pytest + 标记块必须存在），与实际守门一致。

## Impact

- 代码：`tests/test_report_formats_default.py`（fixture 解耦）、`README.md`（恢复 AUTO-GENERATED 标记块，由生成器写入）。无 `medeval/` 运行期代码改动、无产品行为变化。
- 风险：极低。修复后全量套件应由 `235 passed, 4 failed` 转为全绿；不触及 `hard_gate.py`（无需 `verify-heuristics`）。
