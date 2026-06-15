## Why

新增/接入一个 chatbot adapter 现在要改**两处核心代码**且彼此重复：

1. `adapter/__init__.py::build_adapter` 是硬编码 `if/elif` + `_SUPPORTED` 元组——违反开闭原则，每加一个类型都要动这个分发函数。
2. `config.py::AdapterCfg.type` 是静态 `Literal["http","openai_compat","openai","doubao","ark"]` + `_COMPAT_TYPES`——与上面那份"支持类型清单"是**两份漂移源**，改一处忘另一处就会出现"config 接受但 build 拒绝"或反之的裂缝。

研发阶段，借"解耦核心、消除硬编码分支"的主线把它收敛成单一真值源。

## What Changes

引入 adapter **注册表作为单一真值源**，实现彻底开闭（新增 adapter 仅在自己文件里声明一次）：

- 新增 `medeval/adapter/registry.py`：
  - `@register_adapter(*type_names, config_key=...)` 装饰器，把"类型名（含 alias）→ (工厂, config 子块键)"登记进模块级注册表。
  - `build_adapter(adapter_type, config)`：查表分发，去掉 `if/elif`；空/None → fail-fast `ValueError`（消息保留 "config.adapter.type is required" + 已支持清单），未知 → `ValueError`（消息保留 "Unknown adapter type" + 清单 + 注册指引）。
  - `supported_adapter_types()` / `config_key_for(type)` 供外部（config 校验）查询。
- `HttpAdapter` / `OpenAICompatAdapter` 各自打上 `@register_adapter(...)`；`adapter/__init__` 导入它们（触发注册）并重导出注册表 API。
- `config.py::AdapterCfg.type` 由静态 `Literal` 改为 `str`，在 `_check_subblock` 校验器里**按注册表**动态校验：未知类型 → 友好报错（列已支持类型）；必需的 config 子块（`config_key_for(type)` 指向的那个）缺失 → 报错。删除 `config.py` 里重复的 `_COMPAT_TYPES`。

## Capabilities

### Modified Capabilities
- `chatbot-adapter`：新增要求"Adapter 工厂必须基于注册表实现开闭扩展"——工厂 MUST 基于注册表分发（禁止硬编码 `if/elif`），新增 adapter MUST 仅需 `@register_adapter` 声明一次即可被工厂与配置校验同时识别；"已支持类型清单"MUST 由注册表单一提供，禁止在工厂与配置 schema 中各维护一份。既有工厂要求（http/openai_compat 别名、空·None·未知 fail-fast）语义不变，叠加于其上。

## Impact

- 代码：新增 `medeval/adapter/registry.py`；`adapter/__init__.py`、`adapter/http.py`、`adapter/openai_compat.py`、`config.py` 调整；新增 `tests/test_adapter_registry.py`，补 `tests/test_config.py` 未知类型用例。
- 行为：现有类型（http + openai_compat/openai/doubao/ark）构造与报错消息保持不变；`build_adapter` 的空/None/未知报错文案不变（现有 `test_smoke` 不破）。config 层未知 adapter 类型的报错从 pydantic 枚举错变为友好的"不被支持 + 候选清单"（更友好，等价 fail-fast）。
- 兼容性：内部重构；对外配置写法、adapter 协议、report 字段均不变。
- 依赖：不引入新依赖；`config → adapter` 单向依赖（无循环，adapter 不依赖 config）。
