# Tasks

## 1. 拆分
- [x] 1.1 新增 `medeval/reporter/transcript_cells.py`：搬入纯内容派生 helper + 常量（`_MAX_CELL_LEN`/`_TRUNCATE_NOTICE`/`_MARK_*`/`_PROFILE_ZH`）
- [x] 1.2 `excel_transcript.py` 改为从 `transcript_cells` 导入；仅保留排版/写入层与布局常量

## 2. 去重 profile 解析
- [x] 2.1 `_write_transcripts` 每 case 调一次 `resolve_profile`；删除 `_module_max_for_result`
- [x] 2.2 `_test_content_cell(result, profile_name)` 改收已解析 profile 名

## 3. 测试
- [x] 3.1 `tests/test_transcript_cells.py`：截断/折行/标红/得分点/比率/turns 折叠 等纯函数
- [x] 3.2 `tests/test_excel_transcript.py` 回归绿（产物等价）

## 4. 验证
- [x] 4.1 全量 `pytest` 绿（322 passed）
- [x] 4.2 真实 config `medeval run --dry-run` 通过
- [x] 4.3 `graphify update .` 刷新图谱
- [x] 4.4 `openspec validate --strict` 通过并归档
