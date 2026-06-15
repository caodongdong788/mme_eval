## Why

全量审计发现：代码侧有少量重构后遗留的不可达死代码；文档侧根 `README.md` / `AGENTS.md`
仍停留在「纯 CLI 框架」时代，未覆盖平台化（`server/` + `frontend/`）、飞书 SSO 登录、改名
（MME / Agent 评测平台）等已落地能力，且存在事实错误（种子集 42 vs 实际 71、规格里
`DATABASE_URL` vs 实现 `MEDEVAL_DATABASE_URL`、四模块权重写死）。

## What Changes

### 死代码清理（不改可观察行为，移除无调用方符号）
- 删 `medeval/reporter/lark_publisher.py` 的 `publish_report_file`（CLI 直接用 `publish_to_lark`，无调用方）。
- 删 `server/auth.py` 的 `require_user`（路由统一用 `get_current_user_optional` + 中间件门禁，无调用方）。
- 前端 `RunDashboardPage.tsx`：删评级分布 stub `gradeData` 及 `{gradeData.length > 0 && null}`。
- 前端 `api.ts`：`http` 由 `export const` 收为模块内 `const`。
- 前端 `RunsPage.tsx`：`reload()` 去掉无人消费的 `return active.length`。

### 文档同步（P0+P1+P2，纯文档不改行为）
- `README.md`：新增「评测平台」章（架构/启动/目录结构）、飞书 SSO 与按用户导出、延迟性能、
  平台新能力清单（benchmark 管理、可配判分模型、run 重名 409/删除、看板 diff）；修正
  种子集 42→71；`profile_match` 表键名对齐 `config.yaml`；产品名统一 MME · Agent 评测平台。
- `AGENTS.md`：区分「判分内核 medeval」与「平台 server+frontend」；平台启动命令；四模块改为
  profile 自适应表述并补 `hard_gate_passed` 轴；品牌统一。
- `.env.example` / `server/README.md`：品牌统一；`DATABASE_URL`→`MEDEVAL_DATABASE_URL` 一致化。
- `openspec/specs/eval-platform-service/spec.md`：修正 `DATABASE_URL`→`MEDEVAL_DATABASE_URL`。
- 各平台/飞书 `spec.md` 的 `## Purpose: TBD` 补写。

## Capabilities

### Modified Capabilities
- `eval-platform-service`: 规格中数据库环境变量名修正为 `MEDEVAL_DATABASE_URL`（与实现一致）。

## Impact

- 代码：`medeval/reporter/lark_publisher.py`、`server/auth.py`、
  `frontend/src/pages/RunDashboardPage.tsx`、`frontend/src/api.ts`、
  `frontend/src/pages/RunsPage.tsx`（均为移除不可达/未用符号）。
- 文档：`README.md`、`AGENTS.md`、`.env.example`、`server/README.md`、
  `openspec/specs/eval-platform-service/spec.md` 及若干 spec Purpose。
- 测试：无新增行为；以全量 `pytest` 绿 + 前端 `tsc` 零报错作为回归保障。
