## 1. 后端 schema 与 service（TDD：先测后码）

- [x] 1.1 在 `server/schemas.py` 新增 `PreviewRejudgeRequest`（承载单条 `CaseLogicOverride` 判据覆盖）与 `PreviewRejudgeResponse`（新 verdicts / 四维分 / 综合分 / 上线判定 + 与当前值 diff）
- [x] 1.2 先写测试：`tests/` 下新增 service 层测试，覆盖「给定冻结留痕 + 判据覆盖 → 重算判定」「零落库/零 bot 调用」「留痕缺失报错」
- [x] 1.3 在 `server/eval_job.py`（或新 helper）实现 `preview_rejudge_case`：复用 `_frozen_cases_and_traces` 取单条用例 `TestCase` + `ConversationTrace`，套用 `_apply_case_overrides` 同语义的判据覆盖，经 `judge_traces` + `score_case` 重算，**不写库、不建 run 目录、不复制留痕**
- [x] 1.4 跑通 1.2 测试转绿

## 2. 后端路由

- [x] 2.1 先写测试：`POST /api/runs/{run_id}/cases/{sample_id}/preview-rejudge` 的 200（返回 diff）/ 400（留痕缺失）/ 404（用例或 run 不存在）
- [x] 2.2 在 `server/routers/runs.py` 实现该端点，调用 1.3 的 service，断言不产生新 `eval_run`、不写 `case_annotation`、不改 `case_result`
- [x] 2.3 先写测试：`GET /api/runs/{run_id}/cases-yaml?sample_id=<sid>` 只返回单条用例 YAML（可被 `load_cases` 解析）；`sample_id` 不在命中集返回 400
- [x] 2.4 扩展 `cases-yaml` 端点支持可选 `sample_id` 过滤，跑绿 2.1 / 2.3

## 3. 前端 API 与编辑器组件

- [x] 3.1 `frontend/src/api.ts` 新增 `previewRejudgeCase(runId, sampleId, payload)`；扩展 `getRunCasesYaml` 支持可选 `sample_id`
- [x] 3.2 `frontend/src/components/EditCriteriaDrawer.tsx` 新增「当前 benchmark 名称」展示属性（`#id「名称」`），看板入口一并传入
- [x] 3.3 `EditCriteriaDrawer` 新增「试判此用例（预览）」动作与预览结果/ diff 展示区，明确标注「仅预览、不改当前 run」（仅在单用例场景启用）

## 4. 前端用例明细页接入

- [x] 4.1 `frontend/src/pages/CaseDetailPage.tsx`：把 HITL 卡片「去改判据(YAML)」从 `navigate` 改为就地打开 `EditCriteriaDrawer`，以带 `sample_id` 的 cases-yaml 预填单条用例 YAML
- [x] 4.2 接入「覆盖当前 benchmark / 另存为新 benchmark」处理器（复用 derive-yaml / overwrite-yaml），并展示当前 benchmark 名称与「覆盖仅改判据源、不改当前 run」提示
- [x] 4.3 更新 HITL 卡片顶部 Alert 文案，反映新的就地编辑 + 试判预览闭环

## 5. 验证与归档

- [x] 5.1 `pytest` 全量转绿（含新增测试），确认 preview 端点零落库、零 bot 调用
- [x] 5.2 前端按 `.cursor/rules/frontend-workflow.mdc` 自审：单一 UI 库、token 单一信任源、无裸 hex
- [x] 5.3 `medeval run --config config.yaml --dry-run` 跑通（确认主链路未受影响）
- [x] 5.4 `graphify update .` 刷新图谱
- [x] 5.5 `openspec validate case-criteria-preview-rejudge --strict` 通过；完成后走 `openspec archive`
