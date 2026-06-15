## Why

当前评测的"完整对话内容"分散在三处：
- `report.md` 只在失败样本段摘录首条 user/assistant
- `report.html` 含完整 trace，但 HTML 在 `trim-report-formats` change 后会被删除
- `report.json` 含全 trace，但是机器格式，评审者打开看体验差

也就是说，`trim-report-formats` 落地后，**评审者无法在用户面产物里看到完整对话流水**。但这恰恰是医学评审最需要的输入：医生评审一条多轮 case，必须按轮次读完用户提问与 bot 回复才能判断"bot 是否合理"。

需求是：**每次评测都另外输出一份"完整问答流水"独立文档，与报告并列**。该文档：
- 涵盖所有 case（不只是失败的），所有轮次（不只是首轮）
- 表格化排布，方便评审者按 case / 按轮次定位
- 飞书表格形式可直接共享给医学评审

## What Changes

- 新增 `medeval/reporter/excel_transcript.py` 模块：每次 `medeval run` 后写出 `outputs/<run>/transcripts.xlsx`
- 该 xlsx 含 2 个 sheet：
  - **Sheet 1 「概览」**：1 行 = 1 case，列：`sample_id` / `level` / `depth` / `scenario` / `passed` / `stability` / `failure_tags`
  - **Sheet 2 「对话流水」**：1 行 = 1 turn，列：`sample_id` / `turn` / `role`（user/bot/system）/ `content`（自动换行）
- 新增 `medeval/reporter/lark_sheet_publisher.py`：把 transcripts.xlsx 上传到飞书表格（用 `lark-cli sheet +import` 或等价 API），返回飞书 sheet URL；失败时降级（不阻断主流程）
- 报告 markdown 末尾追加一行 `**完整对话流水**：<lark_sheet_url>`，让评审从报告链接跳过去
- 命名约定：飞书 docx = `{run_name} · 评测报告`、飞书 sheet = `{run_name} · 对话流水`
- 修改 `reporting/spec.md` 新增"对话流水独立文档"需求与"飞书表格上传"需求

## Capabilities

### Modified Capabilities

- `reporting`：新增"评测必须输出 transcripts.xlsx 独立文档"约束 + "transcripts.xlsx 必须发布为飞书表格"约束。

## Impact

**受影响代码**

- `medeval/reporter/excel_transcript.py`（新建）—— 用 `openpyxl` 写双 sheet xlsx
- `medeval/reporter/lark_sheet_publisher.py`（新建）—— `publish_xlsx_to_lark(path, parent_folder_token, title)` 接口；底层调 `lark-cli` 子命令上传 xlsx 转飞书 sheet
- `medeval/reporter/__init__.py` —— 暴露 `write_transcripts_xlsx` 与 `publish_sheet_to_lark`
- `medeval/cli.py` —— `medeval run` 在生成 markdown / json 之后调用 `write_transcripts_xlsx` + `publish_xlsx_to_lark`；把返回的 sheet URL 注入 markdown 末尾后再发飞书 docx
- `medeval/reporter/markdown_report.py` —— 接受可选 `transcripts_url` 参数，渲染到报告末尾
- `pyproject.toml` / `requirements.txt` —— 新增 `openpyxl>=3.1` 依赖
- `tests/test_excel_transcript.py`（新建）—— 断言 xlsx 双 sheet 结构、内容完整性、列宽、自动换行
- README "评测产物" 段更新

**不受影响**

- Adapter / Runner / Judge 行为完全不变
- HardGate / Rule / LLM Judge fingerprint 不变
- `report.json` / `report.md` 的现有内容不变（只追加一行 transcript URL）
- `trim-report-formats` change 中确立的"json 永远写、markdown 默认产物"完全兼容

**版本对比影响**

- 不影响 fingerprint
- transcripts.xlsx 不参与 `diff_runs`（diff 仍只看 JSON）

**Breaking change 风险**

- 新增 `openpyxl` 依赖；现有用户 venv 必须 `pip install openpyxl`
- 飞书表格上传依赖 `lark-cli sheet +import` 或相关命令；该命令在用户的 lark-cli 不支持时必须给清晰报错并降级（仅本地 xlsx，不阻断）

**评测成本**

- 写 xlsx：本地 IO，对 40 case × 5 turn 量级 < 1s
- 飞书表格上传：1 次 API 调用，< 5s
- 总增量 < 10s
