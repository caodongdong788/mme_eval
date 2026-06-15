## Why

我们已有"质量"（评分/评级）与"延迟"（`latency_summary`，仅观测）两件套，但还缺"成本"——无法回答"这个 bot 一次对话烧多少 token / 多少钱""哪类用例最贵"。adapter 其实**已经**把 OpenAI 风格 `usage` 采进了 `ChatResponse.raw`，但 `store_raw` 默认 `on_error` 会在成功轮次落盘时清空 raw，数据白白丢掉。本期照搬现成的延迟管线（trace → result → report → 报告/diff → 平台落库 → 看板），平行补一条 **token/cost 观测**管线：先有数据、进报告、上看板，但**仅观测、不计分、不否决**，补齐"质量+延迟+成本"三件套。

## What Changes

- adapter 调用成功时，runner MUST 当场从 `ChatResponse.raw` 归一化抽取 token usage 写入 trace（**不依赖 `raw_responses` 存活**，规避 `store_raw` 裁剪）。
- 在 `ConversationTrace` 保留逐轮 token 用量；在 `CaseResult` 逐 run 记录会话总 token；在 `RunReport` 聚合 token 统计。
- 当 `config.yaml` 配置了单价时，聚合层按"仅观测"口径折算成本（cost），未配置则只出 token、cost 标 N/A。
- markdown 报告与 diff 各新增"成本 / Token（仅观测）"段，明确标注**不计分、不否决**；adapter 出错的 run 不污染统计。
- 评测平台 run 级落库 `token_summary`、case 级落库总 token / cost，看板新增一栏成本/Token 卡片。
- MVP 仅支持 `openai_compat` adapter 的 usage 形状（豆包/方舟/OpenAI/DeepSeek 等），`http` adapter 认不出则留空。

## Capabilities

### New Capabilities
<!-- 无新增 capability -->

### Modified Capabilities
- `chatbot-adapter`: `ChatResponse.raw` 在 LLM 返回 usage 时 MUST 包含可归一化的 token 用量字段。
- `dialog-runner`: 每轮 adapter 调用成功时 MUST 当场采集 token 用量写入 trace；N-runs 下逐次记录会话总 token。
- `reporting`: 报告与 diff MUST 呈现 token/cost 统计且明确标注"仅观测、不计分"；单价缺省时 cost 显示 N/A。
- `eval-platform-service`: run/case 落库 MUST 包含 token/cost 观测字段。
- `eval-platform-dashboard`: 看板 MUST 展示成本/Token 卡片（无数据时友好提示）。

## Impact

- 代码：`medeval/models.py`（trace/result/report 增 token 字段）、`medeval/runner/executor.py`（当场抽取 usage）、`medeval/runner/voting.py`（折叠 per-run tokens）、`medeval/reporter/aggregator.py`（`_token_summary` + cost）、`medeval/reporter/markdown_report.py`、`medeval/reporter/diff.py`、`medeval/config.py` + `config.yaml`（新增 `cost` 段）、`server/{schemas,models_db,ingest}.py`、`frontend/src/{api.ts,pages/RunDashboardPage.tsx}`、`tests/`。
- 兼容性：所有新增字段带默认值（空列表 / 空 dict），历史 `report.json`、现有判分行为、延迟管线完全不变；`models_db` 新增列对 SQLite 靠列默认值兼容。
- 依赖：无新增第三方依赖（usage 已由 adapter SDK 提供，cost 仅本地乘单价）。
- 不触碰核心节点 `TestCase` / `BaseJudge` / `FailureTag`，不改任何 `hard_gate.*` 逻辑。
