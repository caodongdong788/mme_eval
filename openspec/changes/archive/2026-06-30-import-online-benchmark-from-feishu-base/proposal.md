# Proposal: 线上 benchmark 支持飞书 Base URL 导入

## Why

线上真实对话当前只能通过 JSONL 文件上传成 benchmark。运营同学已有飞书 Base 表记录真实会话，字段按轮次拆分为「第 N 轮用户输入 / Cx 输出」，需要在 Benchmark 库里直接粘贴 Base URL 导入，并完整保留每轮对话。

## What

- `POST /api/benchmarks` 在 `source=online` 时复用现有入口：可上传 JSONL 文件，也可提交 `source_url` 飞书 Base URL。
- 后端按入参分流：有 `source_url` 则以当前登录用户飞书 token 读取 Base；否则按现有 JSONL 转换。
- Base 记录转换为 `source=online` YAML case，MUST 按 1～4 轮写入完整 `turns`（user/assistant 成对，空轮跳过）。
- 前端上传弹窗在选择「线上」时，同一块入口允许填写飞书 URL 或拖拽 JSONL，并调整文案。
- 线上用例预览展示多轮对话。

## Impact

- `server/feishu_base.py`、`server/benchmarks.py`、`server/routers/benchmarks.py`
- `tests/server/test_benchmarks.py`、`tests/server/test_benchmarks_api.py`、新增飞书 Base 客户端测试
- `frontend/src/pages/BenchmarksPage.tsx`、`frontend/src/hooks/useBenchmarksPage.ts`
- `frontend/src/components/OnlineCasePreview.tsx` 及测试
- OpenSpec: `eval-platform-service`, `eval-platform-dashboard`
