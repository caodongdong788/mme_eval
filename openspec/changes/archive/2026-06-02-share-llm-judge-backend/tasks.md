# Tasks

## 1. 后端
- [x] 1.1 新增 `medeval/judges/llm_backend.py`：`LLMBackend`（`_build_client` openai/azure 双分支 + `chat_json` 退避循环 + api_key 缺失告警，`owner` 入日志）
- [x] 1.2 新增 `tests/test_llm_backend.py`：provider 分支、缺 key 告警、`RateLimitError` 退避（patch `asyncio.sleep`）

## 2. 接线
- [x] 2.1 `judges/llm.py`：`enabled` 时构造 `self._backend`，`_call` 改薄封装；删除 `_build_client`
- [x] 2.2 `judges/scoring_point.py`：同上
- [x] 2.3 `judges/semantic_adjudicator.py`：同上
- [x] 2.4 清理三处不再使用的 import（`os`/`random`/`asyncio`/`json` 视残留情况）

## 3. 验证
- [x] 3.1 `pytest`（全量绿，含 monkeypatch `_call` 用例）— 257 passed（+8 新增 backend 测试）
- [x] 3.2 三判官 `fingerprint()` 与重构前逐一一致（`test_judge_fingerprint` 通过）
- [x] 3.3 `medeval verify-heuristics` 通过
- [x] 3.4 真实 1-case `medeval run` 跑通、口径对拍无回归（azure+openai 两分支均经实跑）
- [x] 3.5 `graphify update .` 刷新图谱
- [x] 3.6 `openspec validate --strict` 通过并归档
