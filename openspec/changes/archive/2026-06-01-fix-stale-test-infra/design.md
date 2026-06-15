# 设计：修复历史测试基线漂移

## 根因与复现
- `pytest -q` → `235 passed, 4 failed`（与功能开发无关，4 个均在改动前后同样失败）。
- **report_formats ×3**：`_write_minimal_config(...)` 把 `cases.include` 指向 `ROOT/cases/L1_medical_knowledge`（已删）。加载 0 条用例 → run 不写 `report.md` → `assert (out_dir / "report.md").exists()` 失败。
- **README ×1**：`README.md` 的 `## 失败归因标签` 段缺少 `<!-- AUTO-GENERATED:failure-tags-start -->` / `-end` 标记。`gen_failure_tags.check()` 走「缺少标记块」分支返回 1 → `test_readme_in_sync_with_enum` 失败。

## 修复方案

### 1. report_formats 测试 fixture 自包含（首选，彻底解耦）
改 `_write_minimal_config`：在 `tmp_path` 下写一个最小合法 `TestCase` YAML（`sample_id` + `scenario` + `level` + 一个 user turn，外加最小 `hard_gates`），并把 `cases.include` 指向该临时目录。这样测试不再依赖仓库 `cases/` 的任何具体路径，未来用例库再重组也不会让这些 e2e 失败。

- 为什么不直接改指向 `cases/_core_safety`：那仍耦合一个会变动的真实目录；自带 fixture 才是稳定的回归基线。
- 被测行为不变：`--limit` + stub adapter 跑出 ≥1 条结果 → reporter 按 `formats` 规则写 `report.md`/`report.json`，断言成立。

### 2. README 标记恢复（用生成器写回）
运行 `python -m medeval.docs.gen_failure_tags --write`：`patch_readme` 命中无标记分支，用 `^## 失败归因标签 ... ^---` 段整体替换为「标题 + 含标记的新块 + ---」，即重新注入 `AUTO-GENERATED` 标记并按当前 `FailureTag` 词表重生成表格（顺带消除手工维护引入的格式/留白漂移）。此后 `check()` 能定位标记块且内容一致。

### 3. spec 校准
既有场景写「在 CI 中…与 git diff 为空」，但本仓库当前非 git 仓库，真正守门是单测 `test_readme_in_sync_with_enum` 调 `check()`。MODIFIED 该需求，把执行契约改为：单测调用 `gen_failure_tags.check()`，README MUST 保留 `AUTO-GENERATED` 标记块；枚举增删改 MUST 重跑 `--write` 同步。其余元数据场景不变（整段拷贝后仅改该场景）。

## 验证
- `.venv/bin/python -m pytest -q` → 期望 `239 passed`（235 + 修复的 4）。
- `python -m medeval.docs.gen_failure_tags --check` → rc 0。
- `openspec validate fix-stale-test-infra --strict` 通过。

## 不做什么（YAGNI）
- 不动 `config.yaml` 里硬编码的 API key（用户明确表示稍后自行处理）。
- 不重构 reporter / FailureTag 运行期逻辑——本次纯属基线修复。
