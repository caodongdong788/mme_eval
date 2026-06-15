# Tasks

- [x] 1.1 `server/eval_job.py::build_rejudge_job`：load_config 后注入阈值覆盖（读 DB → apply）
- [x] 1.2 测试：阈值改 0.90 后重判 → 知识档 pass_rule.min_composite=0.90 且保留 gates
- [x] 1.3 测试：未配置覆盖时重判行为不变（pass_rule == config.yaml 原值）
- [x] 1.4 `pytest` 全量绿（537 passed）；`graphify update .`
- [x] 1.5 `openspec validate --strict` 后 archive；同步 server/README、AGENTS、前端文案
