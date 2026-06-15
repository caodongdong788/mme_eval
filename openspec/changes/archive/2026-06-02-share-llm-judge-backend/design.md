# Design — 共享 LLM judge 后端

## 背景与约束

三处 LLM 判官的 client/重试逻辑近乎复制。本次只做**内部去重**，硬约束：

1. **判分指纹零变化**：`fingerprint()` 已排除 `api_key/base_url/api_version/default_headers`，且不含 client 对象；只要不动各 `fingerprint()` 字典内容即可保证不变。
2. **单测不破**：`tests/` 通过 monkeypatch `judge._call` 注入假响应（`test_self_consistency` / `test_semantic_adjudicator` / `test_scoring_point` / `test_clinical_benchmark_migration`）。因此 `_call` 必须**仍是各判官实例上的方法**，签名与返回值不变。
3. **判分结果零变化**：纯重构，行为对拍。

## 方案：`LLMBackend` 薄后端 + 判官内 `_call` 薄封装

```
medeval/judges/llm_backend.py
  class LLMBackend:
    __init__(provider, api_key, api_key_env, base_url, api_version, default_headers, owner)
      -> self._client = self._build_client()
    _build_client()            # openai/azure 双分支，api_key or "dummy"，缺失告警(owner)
    async chat_json(model, prompt, temperature, max_retries=4) -> dict
                               # RateLimitError 指数退避循环，返回 json.loads(text)
```

判官侧（`enabled` 时）：

```python
self._backend = LLMBackend(provider=..., api_key=..., api_key_env=..., base_url=...,
                           api_version=..., default_headers=..., owner="LLMJudge")
# 旧 self._client 不再需要

async def _call(self, model, prompt):           # LLMJudge：签名/返回不变
    data = await self._backend.chat_json(model, prompt, self.temperature)
    return data.get("scores", {}) or {}, data.get("reasons", {}) or {}
```

- ScoringPointJudge `_call(prompt)`：`data = await self._backend.chat_json(self.model, prompt, self.temperature)` 后解析 `results`。
- SemanticRuleAdjudicator `_call(model, prompt)`：`return await self._backend.chat_json(model, prompt, self.temperature)`（裸 dict）。

### 为什么是薄后端而非基类继承

判官已继承 `BaseJudge`（定义 `name/judge/fingerprint` 契约）。client/重试是**正交的 IO 关注点**，用组合（注入后端）比多继承/混入更清晰，也便于单测直接替换 `_backend` 或 `_call`。

### owner 参数

仅用于日志可读性（`"%s 触发限速 ..."` / `"%s enabled 但 api_key 未设置"`）。不影响行为、不进指纹。

## 不做的事

- 不改 provider 支持范围（仍 openai/azure）。
- 不改 `max_retries`/退避公式/温度/`response_format`。
- 不合并三个判官的 prompt 或解析逻辑（各自业务语义不同）。
- 不动 `cli._build_judges` 的判官装配（除非注入 backend 需要——实际不需要，判官内部自建 backend）。

## 验证

- `pytest`（全量）：含 self-consistency / adjudicator / scoring_point / migration 的 monkeypatch 路径。
- `tests/test_llm_backend.py`（新增）：fake openai client 验证 provider 分支与 `RateLimitError` 退避（用极小 sleep 或 patch `asyncio.sleep`）。
- 三判官 `fingerprint()` 在重构前后逐一比对（`test_judge_fingerprint` 已守门）。
- `medeval verify-heuristics` + 真实 1-case run 口径对拍（无外网时 LLM 判官 enabled=false 路径不触发，确认无回归）。
