## ADDED Requirements

### Requirement: 所有走 LLM 的判官必须复用同一 LLM client 后端

所有需要调用 LLM 的判官（LLMJudge、ScoringPointJudge、SemanticRuleAdjudicator）MUST 复用同一个 LLM client 后端（`medeval/judges/llm_backend.py` 的 `LLMBackend`），由该后端统一负责：

1. provider 客户端构建（`openai` / `azure` 双分支，`api_key` 缺失时回退 `"dummy"` 并告警，透传 `default_headers`）；
2. 限速退避调用：`RateLimitError` 触发指数退避（最多 4 次额外重试，单次最长约 40s），返回解析后的 JSON dict。

各判官 MUST NOT 各自复制 client 构建与退避循环；判官只保留各自的 prompt 组装与返回 JSON 的结构解析。该后端的调用配置（`api_key` / `base_url` / `api_version` / `default_headers`）MUST NOT 进入任何判官的 `fingerprint()`，以保证切镜像 / 切网关不被误判为判分逻辑变化。

本次重构 MUST 保持判分结果与各判官 `fingerprint()` 一字不变（纯内部去重）。

#### Scenario: 切换网关 base_url 不改变判分指纹

- **当** 仅修改某 LLM 判官的 `base_url` / `default_headers`（如从直连切到内部网关）
- **那么** 该判官的 `fingerprint()` 必须保持不变，不触发"判分逻辑变化"的历史重判

#### Scenario: 限速退避由后端统一处理

- **当** 任一 LLM 判官调用 LLM 时遭遇 `RateLimitError`
- **那么** 由共享后端执行统一的指数退避重试（最多 4 次），三个判官的退避行为一致，无需各自维护重试循环

#### Scenario: 后端可被单测替换

- **当** 单测需要注入假响应
- **那么** 既可替换判官实例上的 `_call`（薄封装），亦可替换其 `_backend`，判官业务逻辑（解析、聚合、救回）保持可独立测试
