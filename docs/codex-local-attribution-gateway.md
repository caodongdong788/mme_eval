# 本地 Codex 归因网关

MME 可以把归因请求交给你本机的 Codex CLI 执行。网关使用 `codex exec` 的结构化 JSON 输出能力；它不是实验性的 Codex App Server，也不需要把 ChatGPT 登录凭据上传到 MME。

## 启动网关

先在本机完成 Codex 登录，并在本仓库环境中执行：

```bash
export CODEX_GATEWAY_TOKEN='请使用随机长字符串'
export CODEX_DEFAULT_MODEL='gpt-5.6-sol'
export CODEX_REASONING_EFFORT='high'
export CODEX_SERVICE_TIER='fast'
uv run uvicorn scripts.codex_attribution_gateway:app --host 127.0.0.1 --port 8787
```

网关默认仅监听本机回环地址。不要将它直接暴露到公网；若生产 MME 需要访问，请经受控 VPN、私网或带鉴权的 SSH 隧道提供一个仅 MME 可访问的 HTTPS 地址。

## MME 模型配置

在“参数配置 → 模型配置”新增模型：

- Provider：`Codex 本地网关`
- 模型：本机 Codex 可用模型名，例如 `gpt-5.6-terra`
- Base URL：本机联调填写 `http://127.0.0.1:8787/v1`；生产填写受控隧道地址并以 `/v1` 结尾
- API Key：与 `CODEX_GATEWAY_TOKEN` 相同

需要“GPT-5.6 Sol / 高 / 快速”时，分别使用 `gpt-5.6-sol`、`high` 和
`fast`。快速模式会提高模型速度，也会增加额度消耗。

该模型可在“开始归因分析”中选择。患者数据仅会发送给该本机 Codex 网关以及其实际使用的 Codex/OpenAI 服务，因此上线前应完成数据合规确认。

## 运行保障

- 单条归因：从首次请求到全部重试共用 300 秒总超时；到时自动将该 Case 标记失败，可单独重新归因。
- 本地网关：默认同样为 300 秒超时、一次执行 1 条，避免本机 Codex 过载；可用 `CODEX_GATEWAY_CONCURRENCY` 调整。
- MME 仍保持归因任务最多同时处理 3 条；每条完成立即落库，失败 Case 可在原任务中继续归因。
