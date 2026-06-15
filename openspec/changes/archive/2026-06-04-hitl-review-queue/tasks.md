# Tasks

## 1. TDD 测试先行（tests/server/test_review_queue.py）
- [ ] 1.1 入队三规则命中/排除（needs_human_review / 红旗+失败 / review_requested / 普通通过不入队）
- [ ] 1.2 annotate 落库 + 多条 + reviewer 取登录名 + 非法 verdict 422 + 未知用例 404
- [ ] 1.3 request-review 置位且幂等
- [ ] 1.4 review-stats 计数 + agree/disagree 率
- [ ] 1.5 `_ensure_additive_columns` 幂等加 review_requested
- [ ] 1.6 不变量：annotate 后判分字段不变

## 2. 后端
- [ ] 2.1 `models_db`：CaseAnnotation 表 + `CaseResultRow.review_requested`
- [ ] 2.2 `db._ADDITIVE_COLUMNS`：case_result.review_requested
- [ ] 2.3 `schemas`：ReviewQueueItemOut / AnnotateRequest / AnnotationOut / ReviewStatsOut
- [ ] 2.4 `routers/runs.py`：review-queue / annotate / request-review / review-stats

## 3. 前端
- [ ] 3.1 `api.ts`：getReviewQueue / annotateCase / requestReview / getReviewStats + 类型
- [ ] 3.2 RunDashboard：待审徽标 + 仅看待审筛选 + 统计卡
- [ ] 3.3 CaseDetailPage：裁定面板 + 已有 annotations 列表 + 去改判据(YAML) 入口

## 4. 收尾
- [ ] 4.1 全量 pytest 绿
- [ ] 4.2 tsc 通过 + `medeval run --dry-run`
- [ ] 4.3 `graphify update .` + `openspec validate --strict` + archive
