# Design — Adapter 插件注册表（单一真值源）

## 注册表表面（`medeval/adapter/registry.py`）

```python
@dataclass(frozen=True)
class _Entry:
    factory: Callable[[dict | None], BaseAdapter]
    config_key: str  # 该类型从 adapter 配置中取哪个子块作为 kwargs

_REGISTRY: dict[str, _Entry] = {}

def register_adapter(*type_names: str, config_key: str):
    """类装饰器：把 type 名（含 alias）登记到注册表。重复登记报错。"""

def build_adapter(adapter_type: str, config: dict) -> BaseAdapter:
    # 空/None → ValueError("config.adapter.type is required. Supported: ...")
    # 未知   → ValueError("Unknown adapter type: ...; Supported: ...; 自定义请用 @register_adapter 注册")
    # 命中   → entry.factory(config.get(entry.config_key))

def supported_adapter_types() -> list[str]: ...   # sorted(_REGISTRY)
def config_key_for(adapter_type: str) -> str | None: ...
```

`factory = lambda section: cls(**(section or {}))`，与现状 `Cls(**(config.get(key) or {}))` 逐字等价。

## 类侧声明

```python
@register_adapter("http", config_key="http")
class HttpAdapter(BaseAdapter): ...

@register_adapter("openai_compat", "openai", "doubao", "ark", config_key="openai_compat")
class OpenAICompatAdapter(BaseAdapter): ...
```

## 注册时机 / 导入拓扑

注册表填充依赖 adapter 类模块被导入（装饰器执行）。`adapter/__init__.py` 已 `from .http import ...` / `from .openai_compat import ...`，故 **import `medeval.adapter` 即完成注册**。

- `config.py` 在校验器内**惰性** `from .adapter import supported_adapter_types, config_key_for`（函数内 import，避免 config 模块导入期就拉起 httpx，且确保走 `adapter/__init__` 触发注册）。
- 依赖方向 `config → adapter` 单向；adapter 包不依赖 config，无循环（已核：http/openai_compat/base 均不 import config）。

## config.py 改动

```python
class AdapterCfg(_Strict):
    type: str                       # 由 Literal 改为 str
    openai_compat: OpenAICompatCfg | None = None
    http: HttpCfg | None = None

    @model_validator(mode="after")
    def _check_subblock(self):
        from .adapter import supported_adapter_types, config_key_for
        if self.type not in supported_adapter_types():
            raise ValueError(
                f"adapter.type={self.type!r} 不被支持。可选："
                f"{', '.join(supported_adapter_types())}"
            )
        key = config_key_for(self.type)            # 'http' | 'openai_compat'
        if key and getattr(self, key, None) is None:
            raise ValueError(f"adapter.type={self.type!r} 但缺少 adapter.{key} 子块")
        return self
```

删除 `config.py` 中重复的 `_COMPAT_TYPES`。`AdapterCfg` 仍保留 `openai_compat` / `http` 两个 typed 子块字段（现有 adapter 复用这两个 section）；将来若新 adapter 引入全新 config 形状，自然需要新增对应 typed 子模型——这属于"新 schema"的固有成本，与"分发开闭"正交。

## 保持不变（行为对拍锚点）

- `build_adapter("", {})` / `(None, {})` → `ValueError` 含 "config.adapter.type is required"
- `build_adapter("mock"/"nonexistent_xyz", {})` → `ValueError` 含 "Unknown adapter type"
- `build_adapter("doubao", cfg)` → `OpenAICompatAdapter`，kwargs 取自 `cfg["openai_compat"]`
- `config.yaml`（openai_compat/azure）校验、`model_dump` 幂等回灌均不变
- CLI monkeypatch 目标 `medeval.cli.build_adapter` 不变

## 测试（TDD）

`tests/test_adapter_registry.py`：
- 注册表含 http + 4 个 compat alias；`supported_adapter_types()` 返回排序清单。
- `config_key_for`：http→"http"，doubao→"openai_compat"，未知→None。
- `build_adapter` 命中：doubao→OpenAICompatAdapter（不触发网络，仅构造；用不需 key 的 http 验证别名取 section 更稳，或对 openai_compat 设 api_key 避免 RuntimeError）。
- 空/None/未知报错文案锚点（与 test_smoke 重叠，保留）。
- 重复注册同名 type → ValueError。
补 `tests/test_config.py`：`{"adapter":{"type":"bogus","openai_compat":{...}}}` → ConfigError 含 "不被支持"。
全量 pytest + verify-heuristics + 真实 config `--dry-run`。
