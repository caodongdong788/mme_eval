## Why

三个走 LLM 的判官——`judges/llm.py`（LLMJudge）、`judges/scoring_point.py`（ScoringPointJudge）、`judges/semantic_adjudicator.py`（SemanticRuleAdjudicator）——各自维护了**逐行近似复制的两套基建**：

1. `_build_client()`：`provider in {openai, azure}` 双分支、`api_key or "dummy"` 回退、`default_headers` 透传、api_key 缺失告警、openai 包缺失报错。
2. `_call()`：`max_retries=4` 的 `RateLimitError` 指数退避循环（`min(40, 2**attempt*5 + jitter)`）+ `response_format=json_object` 调用。

三份实现的唯一实质差异是**返回 JSON 的解析方式**（llm 取 `scores/reasons`、scoring_point 取 `results`、adjudicator 取裸 dict）。基建复制带来的风险：改重试/超时/限速策略或新增 provider/网关头时要同步改三处，易漂移；本期刚加的 self-consistency 多采样也在三处各自演化。

`api_key` / `base_url` / `api_version` / `default_headers` 本就被排除在各判官 `fingerprint()` 之外（属"调用配置"），因此**抽取共享 client 后端不改变任何判分指纹，可纯口径对拍验证**（判分结果零变化）。

研发阶段不考虑历史兼容，可直接重构内部实现。

## What Changes

- 新增 `medeval/judges/llm_backend.py`：`LLMBackend` 统一 client 构建 + 重试/退避调用：
  - `__init__(provider, api_key, api_key_env, base_url, api_version, default_headers, owner)` 内部 `_build_client`，保留 api_key 缺失告警（用 `owner` 区分判官名）。
  - `async def chat_json(model, prompt, temperature, max_retries=4) -> dict`：执行退避循环、返回 `json.loads(text)` 原始 dict。
- 三个判官改为持有 `self._backend`（仅 `enabled` 时构造），各自 `_call` 退化为**薄封装**：调用 `backend.chat_json(...)` 后按各自结构解析。删除三处重复的 `_build_client` 与退避循环。
- 各判官 `_call` 的方法签名与返回值保持不变（单测靠 monkeypatch `judge._call`，必须不破）。
- 各判官 `fingerprint()` 内容**一字不改**（指纹零变化）。

## Capabilities

### Modified Capabilities
- `judging-pipeline`：明确"所有走 LLM 的判官必须复用同一 LLM client 后端（统一 provider 构建与限速退避），且该后端配置不进入判分指纹"，把原先散落三处的隐式约定固化为显式要求。

## Impact

- 代码：新增 `medeval/judges/llm_backend.py`；改 `medeval/judges/llm.py`、`scoring_point.py`、`semantic_adjudicator.py`（删重复基建、注入 backend）；新增 `tests/test_llm_backend.py`。
- 行为：判分结果与指纹零变化（纯重构）；现有 monkeypatch `_call` 的单测继续通过。
- 兼容性：内部重构，无对外 schema / report 字段变化。
- 依赖：不引入新依赖（仍只依赖可选 `openai`）。
