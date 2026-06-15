## ADDED Requirements

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
