# Tasks

- [x] 1. Server 实现：`DIMENSION_MAX` 重配（五维和=10）、`_online_judge_prompt` 加证据先行+三档区间锚点、`ONLINE_JUDGE_PROMPT_VERSION` v1→v2
- [x] 2. Frontend 实现：`ONLINE_DIMENSIONS` 满分与后端对齐
- [x] 3. Test：新增 `test_dimension_max_sums_to_ten` 锁死五维和=10 与两维新满分
- [x] 4. 验证：`pytest tests/server/`（275 passed）、`cd frontend && npm run verify`（全绿）、`openspec validate --strict`
- [x] 5. 审查与收尾：子 Agent ponytail-review（可提交，无过度工程）、CodeRabbit（CLI 已装但未登录，`coderabbit review` 需 `auth login`，本次未跑）、Graphify 结束刷新（缺 LLM API key 语义抽取阻塞，已记录）、OpenSpec archive
