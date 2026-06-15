# Tasks

- [x] 1. graphify update . 刷新图谱（启动）
- [x] 2. TDD：扩展 `tests/test_langfuse_tracing.py`（每条用例独立 trace + session=run_name 分组 + trace_url 捕获落到 `ConversationTrace.langfuse_trace_url` + 关闭/未配置 no-op）；后端用例明细暴露 url 的测试
- [x] 3. `medeval/observability/langfuse_tracing.py`：`conversation(session_id=...)`、新增 `current_trace_id()` / `trace_url()`
- [x] 4. `medeval/models.py`：`ConversationTrace` 新增 `langfuse_trace_url: str | None = None`
- [x] 5. `medeval/runner/executor.py`：`_run_one` 透传 `run_name`，会话 span 设 session 并捕获每条用例 trace_url；`run_cases` 透传 `run_name`
- [x] 6. `medeval/service.py`：`run_traces` 透传 `run_name`；`evaluate` 去掉 run 级 root span（改为每条用例独立 trace）
- [x] 7. `config.yaml`：`observability.langfuse.enabled: true`；`.env.example` 补 `LANGFUSE_*` 占位
- [x] 8. 后端：用例明细 API 暴露每条用例 `langfuse_trace_url`（schema/响应）
- [x] 9. 前端：用例明细每条用例「追踪链路」入口（URL 为空隐藏）+ `api.ts` 类型
- [x] 10. 验证：全量 pytest + 前端 tsc/build + graphify update . + `medeval run --config config.yaml --dry-run` + `openspec validate --strict` 后归档
