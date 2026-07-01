# Tasks: add-cx-agent-adapter

- [x] OpenSpec delta: chatbot-adapter / evaluation-cli
- [x] 测试先行：cx-agent adapter SSE、session 映射、错误路径
- [x] 测试先行：registry/config 识别 `cx_agent`
- [x] 实现 `medeval/adapter/cx_agent.py` 并注册导出
- [x] 更新 `medeval/config.py` 的 `CxAgentCfg`
- [x] 收敛 `config.yaml` 到 cx-agent 被测对象
- [x] 运行相关 pytest、`medeval validate`、`medeval run --dry-run`
- [x] `openspec validate --strict` + archive
