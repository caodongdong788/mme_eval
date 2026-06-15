# Tasks

## 1. TDD
- [ ] 1.1 入队：普通 release_passed=false（非红旗、非 needs_review）也入队，原因含 release_failed
- [ ] 1.2 通过用例仍不入队
- [ ] 1.3 GET /api/config/failure-tags 返回非空映射且含 missed_red_flag→漏报红旗

## 2. 后端
- [ ] 2.1 `_queue_reasons` 增加 release_failed
- [ ] 2.2 `config.router` 增加 failure-tags 端点

## 3. 前端
- [ ] 3.1 `api.ts`：getFailureTagLabels
- [ ] 3.2 看板：筛选条件按 run 记忆（sessionStorage）+ Select 受控回显
- [ ] 3.3 失败标签中文化（看板列 + 标签分布图 + 用例详情 verdict 列）

## 4. 收尾
- [ ] 4.1 pytest 绿 + tsc + dry-run + graphify update + openspec validate/archive
