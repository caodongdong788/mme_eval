# Tasks

## 1. 注册表
- [x] 1.1 新增 `medeval/adapter/registry.py`：`register_adapter` 装饰器 + `_REGISTRY` + `build_adapter` + `supported_adapter_types` + `config_key_for`
- [x] 1.2 `HttpAdapter` / `OpenAICompatAdapter` 打 `@register_adapter(...)`
- [x] 1.3 `adapter/__init__.py`：移除旧 `_SUPPORTED` + if/elif `build_adapter`，改为从 registry 重导出（导入类触发注册）

## 2. config 单一真值源
- [x] 2.1 `config.py::AdapterCfg.type` 由 `Literal` 改 `str`，`_check_subblock` 惰性按注册表校验；删除重复 `_COMPAT_TYPES`

## 3. TDD 测试
- [x] 3.1 `tests/test_adapter_registry.py`：注册集合 / config_key_for / build 命中 / 空·None·未知报错 / 重复注册报错
- [x] 3.2 `tests/test_config.py` 补：未知 adapter.type → ConfigError 含"不被支持"

## 4. 验证
- [x] 4.1 全量 `pytest` 绿（293 passed，含 test_smoke / test_config / e2e 回归）
- [x] 4.2 `medeval verify-heuristics` 通过
- [x] 4.3 真实 config `medeval run --dry-run` 通过
- [x] 4.4 `graphify update .` 刷新图谱
- [x] 4.5 `openspec validate --strict` 通过并归档
