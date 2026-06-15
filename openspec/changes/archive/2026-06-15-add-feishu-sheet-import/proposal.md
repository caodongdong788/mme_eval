# Proposal: 飞书电子表格导入评测用例（import-feishu）

## Why

业务方在飞书电子表格维护 benchmark（测试内容、得分点、多轮用户+Bot 对话），手工改写成 `TestCase` YAML 成本高。需要脚本从表格拉取并生成可 `medeval validate` 的用例文件；得分点列可选，缺失时由 LLM 补全判据。

## What Changes

- 新增 `medeval/import_feishu/`：拉表（`lark-cli`）、解析固定表头、组装 `TestCase`、可选 LLM 富化。
- 新增 `scripts/import_benchmark_from_feishu.py` 与 CLI 子命令 `medeval import-feishu`。
- 表头：`测试内容` / `得分点明细` / `轮数` / `第N轮 (用户+Bot)`（与业务表格一致）。
- 产出 YAML + `*.import_report.json`；默认跑 `medeval validate`。

## Non-Goals

- 不做 Web 上传 UI；不支持多维表格 Base（后续扩展）。
- 不改综合分公式；不自动写入平台 benchmark 库。

## Risks

- 依赖本机 `lark-cli auth login`；表格结构变更需同步解析器。
- LLM 生成判据需人工抽检（报告标 `needs_review`）。
