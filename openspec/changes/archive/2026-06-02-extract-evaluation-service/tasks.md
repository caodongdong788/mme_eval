# Tasks

## 1. 服务层
- [x] 1.1 新增 `medeval/service.py`：`ProgressObserver` Protocol + `NullProgress`
- [x] 1.2 迁入并公开 `build_judges` / `build_adjudicator`（自 cli）
- [x] 1.3 `evaluate(config, cases, adapter, judges, adjudicator, *, progress=NullProgress()) -> RunReport`（搬运原 `_go` 全流程 + build_report，逻辑不改）
- [x] 1.4 `resolve_diff_target` + `write_core_artifacts`(+`Artifacts`) + 迁入 `_find_previous_run`

## 2. TDD 测试
- [x] 2.1 `tests/test_service.py`：evaluate(stub adapter)→RunReport + 记录式 observer 事件 / resolve_diff_target 四态 / write_core_artifacts tmp 写盘 + diff 有无 prev

## 3. CLI 变薄
- [x] 3.1 `cli` 内实现 `RichProgress`（包 rich Progress，映射 phase key→task）
- [x] 3.2 `cli.run` 改为：构造 adapter/judges/adjudicator 注入 `evaluate` → 打印总览 → `resolve_diff_target`+`write_core_artifacts` → 飞书 sheet → `write_markdown` → 飞书 doc → 阈值+exit
- [x] 3.3 删除 cli 内已迁出的 `_build_judges`/`_build_adjudicator`/`_find_previous_run`，清理 import

## 4. 验证
- [x] 4.1 全量 `pytest` 绿（含新 test_service + 现有 e2e 回归）
- [x] 4.2 `medeval verify-heuristics` 通过
- [x] 4.3 行为对拍：e2e `test_report_formats_default` 全程经 evaluate + write_core_artifacts 回归绿；真实 config `--dry-run` 通过
- [x] 4.4 `graphify update .` 刷新图谱
- [x] 4.5 `openspec validate --strict` 通过并归档
