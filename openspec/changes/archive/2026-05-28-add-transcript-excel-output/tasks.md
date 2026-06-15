## 1. 依赖

- [x] 1.1 `pyproject.toml` 主依赖列表新增 `openpyxl>=3.1`（作为核心 reporting 依赖，不放 optional）；同时把不再使用的 `jinja2` 从核心 deps 移除（HTML 模板已在 trim-report-formats 中删除）
- [x] 1.2 `pip install openpyxl>=3.1` 完成；`pytest tests/` 跑过（70 → 87，无冲突）

## 2. Excel writer 实现

- [x] 2.1 新建 `medeval/reporter/excel_transcript.py::write_transcripts_xlsx(report, path)`
- [x] 2.2 Sheet 1 「概览」：列序 sample_id / level / depth / scenario / passed / stability / failure_tags；header 加粗；列宽 6~40；freeze_panes="A2"
- [x] 2.3 Sheet 2 「对话流水」：列序 sample_id / turn / role / content；content 列宽 80 + wrap_text；freeze_panes="A2"
- [x] 2.4 turn 编号规则实现：循环外维护 `user_turn_idx`，user 自增、bot 跟随、system 标 0
- [x] 2.5 单 cell > 32767 字符做截断，追加 "（已截断，完整内容见 report.json）"；`_truncate` 单元测试覆盖
- [x] 2.6 `tests/test_excel_transcript.py` 新增 8 用例：基本结构、列序、行数、turn 编号、wrap_text、freeze_panes、截断、stability N=1、failure_tags 拼接

## 3. 飞书 Sheet publisher

- [x] 3.1 新建 `medeval/reporter/lark_sheet_publisher.py::publish_xlsx_to_lark(xlsx_path, parent_folder_token, title)`
- [x] 3.2 走 `lark-cli drive +import --target-type sheet` 路径；URL 解析尝试多种嵌套 path（`data.file.url` / `data.url` / `data.document.url` / `file.url`）兼容不同 lark-cli 版本
- [x] 3.3 错误处理对齐 markdown publisher：lark-cli 不存在 → None + warning；非零退出 → None + error log；超时 120s（xlsx 上传比 markdown 慢，给宽容窗口）；JSON 解析失败 → None
- [x] 3.4 `tests/test_lark_sheet_publisher.py` 新增 6 用例：lark-cli 缺失 / xlsx 缺失 / argv shape & URL 提取 / 非零退出 / 非 JSON 输出 / alt URL path

## 4. CLI 接入

- [x] 4.1 `medeval/cli.py::run` 在生成 markdown 前先 `write_transcripts_xlsx`，再 `publish_xlsx_to_lark`，最后 `write_markdown(transcripts_url=...)` 让 markdown 末尾带 sheet URL
- [x] 4.2 `lark.enabled: false` 时跳过 sheet 上传，markdown 末尾追加本地 xlsx 路径（fallback）
- [x] 4.3 sheet URL 写盘到 `out_dir / "lark_transcripts_url.txt"`（与 `lark_url.txt` 对称）

## 5. Markdown footer 追加

- [x] 5.1 `medeval/reporter/markdown_report.py::render_markdown` / `write_markdown` 新增可选参数 `transcripts_url`；非空时追加 `\n\n---\n\n**完整对话流水**：<url>`
- [x] 5.2 同时支持 https 和本地 xlsx 路径作为 url 输入（reporter 不做协议判断，CLI 决定 fallback 内容）
- [x] 5.3 `tests/test_markdown_transcripts_url.py` 新增 3 用例：无 URL / https URL / 本地路径

## 6. 文档与 spec

- [x] 6.1 README "快速开始" 列出 `report.md` / `transcripts.xlsx` / `report.json` / `lark_url.txt` / `lark_transcripts_url.txt` 五种产物
- [x] 6.2 `openspec/specs/reporting/spec.md` 主 spec 合入两条 ADDED 需求 + 9 个场景（transcripts.xlsx 结构 / 飞书 sheet 上传与 fallback）
- [x] 6.3 `openspec validate add-transcript-excel-output --strict` 通过

## 7. 端到端验证

- [x] 7.1 用 mock RunReport（5 case × 5 message）跑完整 reporter pipeline：transcripts.xlsx 双 sheet 行数正确（6/26）；report.md 末尾含 transcripts URL
- [x] 7.2 用 openpyxl `load_workbook` 抽查 sheet 内容、freeze_panes、wrap_text、列宽、turn 编号 / role 重命名（assistant→bot）/ failure_tags 拼接 / 截断行为，全部通过单元测试
- [x] 7.3 飞书表格 URL 上传：单元测试用 monkeypatch subprocess 验证 argv shape + URL 解析 6 路径变体；真实 lark-cli 集成留作 7.4 人工 verify
- [x] 7.4 [人工触发] 真实 lark-cli 跑一次 multi_turn baseline 后人工打开飞书 sheet 链接确认数据正确

## 8. 归档

- [x] 8.1 [人工触发] PR review 通过、合入主干后运行 `/opsx-archive-change`
