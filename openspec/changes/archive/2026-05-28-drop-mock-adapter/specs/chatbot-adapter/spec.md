## REMOVED Requirements

### Requirement: 系统必须提供基于关键词模拟的 Mock Adapter

**Reason**: `MockAdapter` 是 P0 期的脚手架，无对真实 chatbot 评测的贡献。保留它会让"配置漏写 adapter type 时静默走 mock 跑出无意义报告"成为默认行为，与 fail-fast 配置哲学冲突。框架成熟后该需求已无存在必要。

**Migration**: 没有用户依赖。如果有人当前仅用 MockAdapter 跑通流程，应该直接配置真实 chatbot（`openai_compat` 或 `http`）。冒烟测试改用 OpenAI 协议响应桩（见 `drop-mock-adapter` change tasks 5）。

## ADDED Requirements

### Requirement: 系统必须 fail-fast 拒绝缺失的 adapter type 配置

`build_adapter(adapter_type, config)` MUST 在 `adapter_type` 为空字符串、None、或不在已注册 adapter 列表中时抛出 `ValueError`，错误消息 MUST 明确指出"`config.adapter.type` is required" 以及当前已支持的 adapter 列表。CLI MUST 在 adapter 构造之前完成该校验，且在错误信息中提示用户检查 `config.yaml` 中的 `adapter.type` 字段。

不允许任何形式的"默认 adapter type"——包括 `config.adapter.type` 字段缺失时回退到任何具体类型（如 `openai_compat`）。理由：评测框架的核心契约是"用户必须显式声明被测对象是谁"；任何隐式回退都违反这条契约。

#### 场景: config 中缺失 adapter.type

- **WHEN** config.yaml 仅有 `adapter: {}`（无 type 字段）
- **THEN** `medeval run` MUST 在加载 case 与跑 adapter 之前以非零退出码退出，stderr 输出类似 `config.adapter.type is required (got empty); supported types: openai_compat, http`

#### 场景: config 中 adapter.type 拼写错误

- **WHEN** config.yaml 中 `adapter.type: "openaai_compat"`（拼写错）
- **THEN** CLI MUST 给出明确报错，列出已支持类型让用户对比；不得静默走默认或 mock

#### 场景: 已支持类型必须保持工作

- **WHEN** config.yaml 中 `adapter.type: "openai_compat"` 且其余字段合法
- **THEN** 框架行为必须与本 change 之前完全一致，不受 fail-fast 改造影响
