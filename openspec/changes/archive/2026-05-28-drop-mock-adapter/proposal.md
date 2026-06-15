## Why

`MockAdapter` 在 P0 时期是为了"无 API key 也能跑通 pipeline"而设计的脚手架。它从来没有真正参与过对 chatbot 质量的评测——评测唯一有意义的输入是真实 chatbot。Mock 留下的副作用反而成了维护负担：

- `medeval/cli.py` 默认 `adapter_cfg.get("type", "mock")`：用户漏配 adapter 时框架"温柔失败"成 mock 跑，跑出来的报告毫无意义但仍走完整流程，掩盖配置失误
- `medeval/models.py` 默认 `adapter_type: str = "mock"`：同样的失静默问题
- `chatbot-adapter` spec 第 30-47 行写着"系统必须提供 MockAdapter"作为正式需求，把 P0 临时脚手架固化成了产品契约
- `tests/test_smoke.py` 依赖 mock 走端到端，导致 smoke 实际只测了"框架 + 一个根本不存在的产品"
- `config.multi_turn_smoke.yaml` 是仅为冒烟而存在的产物，与正式 config.yaml 的字段集时不时漂移
- `medeval/adapter/mock.py` 自己 156 行代码 + 一堆症状关键词、紧急回复模板，需要随医学认知更新而维护

`add-multi-turn-evaluation` 之后，框架已经稳定到不需要 mock 当脚手架。继续保留只是**让"配置失误悄悄走错路径"成为框架默认姿态**，与 `harden-evaluation-determinism` 的"复现优先 / fail-fast"哲学相悖。

## What Changes

- 删除 `medeval/adapter/mock.py` 整文件
- 删除 `medeval/adapter/__init__.py` 中 `MockAdapter` 的 import / 注册分支 / `__all__` 暴露
- `medeval/cli.py` 中两处 `adapter_cfg.get("type", "mock")` 改为：缺失时直接 `raise ValueError("config.adapter.type is required (no default)")`，fail-fast
- `medeval/models.py` 中 `adapter_type: str = "mock"` 改为 `adapter_type: str = ""`，并在 `RunReport` 校验里要求非空
- 删除 `tests/test_smoke.py` 中所有 mock 依赖；用一段使用 `httpx_mock`/`respx` 之类的 HttpAdapter 桩或 `OpenAICompatAdapter` 桩替代，让 smoke 真测"框架打到 OpenAI 协议层这件事"
- 删除 `config.multi_turn_smoke.yaml`（其唯一用途就是 mock smoke）
- 修改 `chatbot-adapter` spec：删除 `需求:系统必须提供基于关键词模拟的 Mock Adapter` 整条需求 + 配套 3 个场景；新增 `需求:系统必须 fail-fast 拒绝缺失的 adapter type 配置` 一条
- `dialog-runner` spec 中如有引用 mock 的字面（grep 后再定夺）一并清理

## Capabilities

### Modified Capabilities

- `chatbot-adapter`：移除 MockAdapter 需求，新增"adapter type 必填 fail-fast"约束。

### Removed Capabilities

无（MockAdapter 不是单独 capability，只是 chatbot-adapter 内的一条需求）。

## Impact

**受影响代码**

- `medeval/adapter/mock.py` —— 删除
- `medeval/adapter/__init__.py` —— 删除 mock 注册
- `medeval/cli.py` —— 两处默认 fallback 改 fail-fast；新增清晰报错文案
- `medeval/models.py` —— `adapter_type` 默认值改为 `""`，校验非空
- `tests/test_smoke.py` —— 重写：用 OpenAI 协议响应桩验证 adapter 调用与 judge 链路
- `config.multi_turn_smoke.yaml` —— 删除
- `openspec/specs/chatbot-adapter/spec.md` —— 删除 mock 需求 + 场景

**不受影响**

- 真实 adapter（`OpenAICompatAdapter` / `HttpAdapter`）行为不变
- 既有 config.yaml / config.l1.yaml / config.multi_turn.yaml 都已显式写 `type: openai_compat`，不受 fail-fast 影响
- Judge / Reporter 逻辑完全不变

**版本对比影响**

- 不影响 fingerprint
- 不影响历史报告（mock-generated 的报告本来就不应作为基线）

**Breaking change 风险**

- 仅当下游用户（如果有）依赖"漏配 adapter 时回退 mock"这个隐式行为时受影响
- 当前知道的 config 文件都显式声明了 `type`，不受影响
- README / CI workflows 中提到 mock 的地方需要 grep 一遍清理
