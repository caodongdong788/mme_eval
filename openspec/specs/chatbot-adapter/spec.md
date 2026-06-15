# Chatbot 适配器（chatbot-adapter）

## Purpose

把"评测框架"和"被测 chatbot 的具体调用方式"解耦。Adapter 是评测框架与被测系统之间的唯一接缝，向上提供统一的异步 `chat(req) -> resp` 协议，向下隐藏 HTTP、SDK、OpenAI 兼容接口等差异。任何新的医疗 chatbot 接入都必须以新增/复用 Adapter 实现完成，禁止把 Bot 特定的协议泄漏到 Runner / Judge / Reporter。

设计原则：

- **异步优先**：所有 Adapter 必须是 `async`，便于 Runner 做高并发；同步实现禁止存在。
- **stateless**：Adapter 不持有对话历史，每次调用都收到完整 messages，由 Runner 负责拼装。这避免了重试与并发场景下的脏状态。
- **失败可追溯**：失败必须以结构化 `ChatResponse.error` 返回，禁止以裸异常向上抛——否则 Runner 的重试和报告就拿不到错误信息。
- **raw 透明**：所有 Adapter 必须保留底层响应的原始字段（如 model、finish_reason、usage、检索片段等）到 `ChatResponse.raw`，便于 hallucination / 工具误用类问题的事后排查。
## Requirements

### 需求:系统必须提供统一的异步 Adapter 抽象基类

系统 MUST 定义 `BaseAdapter`，其 `chat(req: ChatRequest) -> ChatResponse` 必须是 `async` 抽象方法。`ChatRequest` 必须包含 OpenAI 风格 `messages` 数组、`session_id`、可选 `metadata`；`ChatResponse` 必须包含 `reply` 字符串、`raw` 字典与可选 `error`。基类必须提供 `close()` 异步钩子用于释放资源（HTTP client、SDK client 等）。

#### 场景:实现一个新 Adapter

- **当** 开发者编写 `class MyBotAdapter(BaseAdapter)` 并实现 `async def chat`
- **那么** 该实现必须能被 Runner 直接复用，且必须能通过 `await adapter.close()` 触发资源释放

#### 场景:Adapter 不得直接抛出网络异常

- **当** 底层 HTTP / SDK 调用抛出 `httpx.ConnectError` 或类似异常
- **那么** Adapter 必须将其捕获并写入 `ChatResponse.error`，`reply` 设为空字符串，函数正常返回，禁止 raise 给上层

### 需求:系统必须 fail-fast 拒绝缺失的 adapter type 配置

`build_adapter(adapter_type, config)` MUST 在 `adapter_type` 为空字符串、None、或不在已注册 adapter 列表中时抛出 `ValueError`，错误消息 MUST 明确指出 "`config.adapter.type` is required" 以及当前已支持的 adapter 列表。CLI MUST 在 adapter 构造之前完成该校验，且在错误信息中提示用户检查 `config.yaml` 中的 `adapter.type` 字段。

不允许任何形式的"默认 adapter type"——包括 `config.adapter.type` 字段缺失时回退到任何具体类型（如 `openai_compat`）。理由：评测框架的核心契约是"用户必须显式声明被测对象是谁"；任何隐式回退都违反这条契约。

#### 场景:config 中缺失 adapter.type

- **当** config.yaml 仅有 `adapter: {}`（无 type 字段）
- **那么** `medeval run` MUST 在加载 case 与跑 adapter 之前以非零退出码退出，stderr 输出类似 `config.adapter.type is required (got empty); supported types: openai_compat, http`

#### 场景:config 中 adapter.type 拼写错误或为已下线的 mock

- **当** config.yaml 中 `adapter.type: "mock"` 或 `"openaai_compat"`（拼写错）
- **那么** CLI MUST 给出明确报错，列出已支持类型让用户对比；不得静默回退到任何默认 adapter

#### 场景:已支持类型必须保持工作

- **当** config.yaml 中 `adapter.type: "openai_compat"` 且其余字段合法
- **那么** 框架行为必须与 fail-fast 改造之前完全一致

### 需求:系统必须提供通用 HTTP Adapter

系统 MUST 提供 `HttpAdapter`，允许通过 `body_template`（包含 `{{messages}}` 和 `{{session_id}}` 占位符）与 `response_path`（点路径，例如 `data.reply`）把任意 HTTP JSON 接口接入评测。`headers` 必须支持 `${ENV_VAR}` 形式的环境变量插值，避免硬编码 token。

#### 场景:body_template 中占位符必须被替换

- **当** `body_template='{"messages": {{messages}}, "session_id": "{{session_id}}"}'`
- **那么** 发出的请求 body 必须是把 messages 序列化为 JSON 数组、session_id 写入字符串后的合法 JSON

#### 场景:response_path 提取嵌套字段

- **当** 响应是 `{"data": {"reply": "你好"}}`，配置 `response_path="data.reply"`
- **那么** `ChatResponse.reply` 必须为 `"你好"`，`raw` 必须为完整 JSON 字典

#### 场景:HTTP 错误必须不抛出

- **当** 接口返回 5xx 或 body_template 序列化失败
- **那么** Adapter 必须捕获并把错误信息写入 `ChatResponse.error`，函数仍然正常 return

### 需求:系统必须提供 OpenAI 兼容接口 Adapter

系统 MUST 提供 `OpenAICompatAdapter`，覆盖 OpenAI / Azure / 火山方舟（豆包）/ DeepSeek 等所有走 `/v1/chat/completions` 的服务。Adapter 必须支持自定义 `base_url`、`model`、`temperature`、`max_tokens`、`api_key_env`（环境变量名）、`system_prompt`（自动注入）以及 `extra_body`（用于豆包等需要的特殊字段，如思考模式）。

#### 场景:system_prompt 在 messages 已无 system 时必须自动注入

- **当** Runner 传入的 messages 中没有 role=system 的条目，且 Adapter 配置了非空 `system_prompt`
- **那么** Adapter 必须在调用底层 API 前将 `{"role": "system", "content": system_prompt}` 插入 messages 首位

#### 场景:system_prompt 已存在时禁止重复注入

- **当** Runner 传入的 messages 第一条已经是 system
- **那么** Adapter 不得再插入额外 system 消息

#### 场景:缺少 API key 时构造必须立即失败

- **当** 配置中 `api_key` 为空，且对应环境变量也不存在
- **那么** 构造 Adapter 必须以 `RuntimeError` 失败，错误信息必须指明应该设置哪个环境变量

#### 场景:必须保留 usage 与 finish_reason 到 raw

- **当** OpenAI 兼容接口返回包含 usage、finish_reason 等元数据
- **那么** `ChatResponse.raw` 必须至少包含 `id`、`model`、`finish_reason`、`usage` 四个字段，便于后续做成本统计与截断诊断

### 需求:系统必须提供根据配置构造 Adapter 的工厂函数

系统 MUST 提供 `build_adapter(adapter_type: str, config: dict) -> BaseAdapter`。`adapter_type` 必须支持 `http`、`openai_compat`（含 alias：`openai`、`doubao`、`ark`），对未知类型（含历史上的 `mock`）必须以 `ValueError` 失败，错误消息中需提示如何在工厂中注册自定义 adapter。

#### 场景:未知 adapter 类型

- **当** `build_adapter("foobar", {})`
- **那么** 必须抛出 `ValueError`，并提示当前已支持的 adapter 类型清单与"自定义 adapter 请在此处注册"的指引

#### 场景:别名解析

- **当** `build_adapter("doubao", cfg)`
- **那么** 必须返回 `OpenAICompatAdapter` 实例，参数取自 `cfg["openai_compat"]`

### Requirement: Adapter 工厂必须基于注册表实现开闭扩展

`build_adapter(adapter_type, config)` 的类型分发 MUST 基于**注册表**实现，禁止以硬编码 `if/elif` 分支枚举类型。系统 MUST 提供 `@register_adapter(*type_names, config_key=...)` 类装饰器，使任一 adapter 类只需在自身定义处声明一次（含 alias 与其 config 子块键）即可被工厂识别。

"已支持 adapter 类型清单" MUST 由注册表单一提供（`supported_adapter_types()`），并 MUST 同时服务于工厂分发与配置 schema 校验——禁止在工厂与配置层各维护一份会漂移的类型清单。重复以同一 `type_name` 注册 MUST 在注册期以 `ValueError` 失败，避免静默覆盖。

本要求与既有"系统必须提供根据配置构造 Adapter 的工厂函数"叠加：现有 `http` / `openai_compat`（alias：`openai`、`doubao`、`ark`）行为、空·None·未知类型的 `ValueError` fail-fast 语义 MUST 保持不变。

#### Scenario: 注册表为类型清单的单一真值源

- **当** 开发者用 `@register_adapter("mybot", config_key="mybot")` 注册一个新 adapter 类
- **那么** `build_adapter("mybot", ...)` 与配置校验 MUST 同时识别该类型，无需修改 `build_adapter` 函数体或在配置 schema 中另行登记类型名

#### Scenario: 重复注册同名类型必须报错

- **当** 两个 adapter 类用同一 `type_name` 调用 `@register_adapter`
- **那么** MUST 在注册时抛出 `ValueError`，避免静默覆盖造成的分发歧义

#### Scenario: 配置层未知类型走注册表校验

- **当** config.yaml 中 `adapter.type` 不在注册表中（如拼写错）
- **那么** 配置加载 MUST fail-fast 报错，并列出注册表中的已支持类型清单

#### Scenario: 已注册类型与别名保持工作

- **当** `build_adapter("doubao", cfg)`
- **那么** MUST 返回 `OpenAICompatAdapter` 实例，参数取自 `cfg["openai_compat"]`，行为与重构前一致

### Requirement: Adapter 在 LLM 返回 usage 时必须保留可归一化的 token 用量

当被测后端在响应中返回 token usage 时，adapter 产出的 `ChatResponse.raw` MUST 包含可被 runner 归一化的 token 用量字段（OpenAI 风格 `usage.prompt_tokens / completion_tokens / total_tokens`）。该字段 MUST 仅作观测数据保留，MUST NOT 影响 `reply` 内容或判分。后端未返回 usage 时 adapter MUST NOT 伪造数值（留空即可）。

#### Scenario: openai_compat 保留 usage

- **WHEN** openai_compat adapter 收到含 `usage` 的成功响应
- **THEN** `ChatResponse.raw["usage"]` MUST 含 `prompt_tokens / completion_tokens / total_tokens`

#### Scenario: 后端无 usage 时不伪造

- **WHEN** 后端响应未携带 usage
- **THEN** `ChatResponse.raw` 中 usage MUST 为空（缺省 `{}`），MUST NOT 出现编造的 token 数

