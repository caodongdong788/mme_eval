# Proposal: add-cx-agent-adapter

## Why

当前默认被测对象仍是临时 `openai_compat`/通用 `http` 配置，无法直接评测 cx-agent 的真实 agentLoop。cx-agent 本地已经提供 `/api/test/chat/send` SSE 测试路由，可绕过登录但保留真实 Agent、工具、DB 会话与多轮上下文。

## What Changes

- 新增 `cx_agent` adapter，专门调用 cx-agent 本地测试 SSE 接口。
- 为 `adapter.cx_agent` 增加严格配置 schema。
- 将默认 `config.yaml` 的被测对象收敛为 cx-agent，删除临时通用 bot 配置块。
- 增加单测覆盖 SSE 解析、session 映射、错误处理与配置注册。

## Scope

- **In**: `medeval/adapter/**`、`medeval/config.py`、`config.yaml`、`tests/test_*`、OpenSpec specs
- **Out**: cx-agent 仓库改动、runner 主链路改动、judge/scoring 口径改动、server/frontend 改动

## Success

- `adapter.type: cx_agent` 能被配置校验与 adapter 工厂同时识别。
- 每个 mme case session 映射到独立 cx-agent session，同一 case 多轮复用同一 session。
- cx-agent SSE `text_delta` 能拼出最终回复，`session`/`message_end`/`error` 事件可追踪。
- 默认配置不再包含临时被测 bot 的 `openai_compat`/`http` 子块。
