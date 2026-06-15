# Tasks

## 1. report_formats 测试 fixture 自包含
- [x] 1.1 改 `tests/test_report_formats_default.py` 的 `_write_minimal_config`：`_write_minimal_case_dir` 在 `tmp_path` 写最小合法用例 YAML，`cases.include` 指向该临时目录（脱离 `cases/L1_medical_knowledge`）
- [x] 1.2 补 `_resolve_out_dir`：按 `outputs/<run>_<时间戳>` 前缀定位输出目录（CLI 落独立时间戳目录，旧断言硬编码无时间戳路径）
- [x] 1.3 三个 e2e 用例转绿，且 `test_formats_html_is_rejected` 仍绿（`4 passed`）

## 2. README AUTO-GENERATED 标记恢复
- [x] 2.1 运行 `python -m medeval.docs.gen_failure_tags --write` 重新注入标记块并按 FailureTag 词表重生成表格
- [x] 2.2 `python -m medeval.docs.gen_failure_tags --check` rc 0；`test_readme_in_sync_with_enum` 转绿

## 3. 验证与收尾
- [x] 3.1 `.venv/bin/python -m pytest -q` 全量转绿（`239 passed`）
- [x] 3.2 `openspec validate fix-stale-test-infra --strict` 通过
- [ ] 3.3 `graphify update .` 更新图谱
- [ ] 3.4 OpenSpec 归档变更
