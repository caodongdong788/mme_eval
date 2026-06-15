## F0 前端零风险工程化
- [x] 1.1 接入 ESLint + Prettier（`eslint.config.js` + `@typescript-eslint` + `react-hooks` + `react-refresh`），加 `npm run lint`
- [x] 1.2 删死代码：`theme.ts::passColor`、`Paragraph`/`Space` 无用导入；`tsconfig` 开 `noUnusedLocals/Parameters`
- [x] 1.3 抽 `src/labels.ts`（DIM_LABEL / PROFILE / STABILITY），替换 4 处重复定义
- [x] 1.4 抽 `src/utils/apiError.ts::formatApiError`（处理 string|array detail），替换散落 catch（22 处）
- [x] 1.5 axios 加 `timeout` + 请求拦截器；保留现有响应拦截器
- [x] 1.6 修复 `theme.ts.palette.chart.ink` ↔ `styles.css --chart-ink` 镜像
- [x] 1.7 验证：`tsc --noEmit` + `lint`(0 error) + `build` 通过

## B0 后端安全
- [x] 2.1 测试先行：`tests/server/test_security_hardening.py`（路径穿越、上传上限、SESSION_SECRET 生产校验）
- [x] 2.2 `medeval/run_slug.py` 消毒（去分隔符/控制字符/`..`，保留中文）+ 新增 `server/paths.py::safe_join`
- [x] 2.3 产物路径（export/_source_out_dir/delete）经 `safe_join` 边界校验
- [x] 2.4 `settings.py` 生产强制非默认 `SESSION_SECRET`（lifespan 校验）；`auth.py` cookie `Secure`
- [x] 2.5 benchmark 上传大小上限（`_read_upload_capped`，413）
- [x] 2.6 写类接口登录：已由 `auth_required` 全局中间件统一守卫（dev 放行为设计），不加冗余依赖
- [x] 2.7 验证：新增测试 + 全量 pytest 608 绿

## F1 前端性能
- [x] 3.1 `App.tsx` 路由 `React.lazy` + `Suspense`
- [x] 3.2 `vite.config.ts` `manualChunks` 拆 vendor（react/antd/recharts）+ chunkSizeWarningLimit
- [x] 3.3 `RunsPage`（active 才轮询 + 可见性暂停 + 回前台刷新）/`PairwisePage`（可见性暂停）
- [x] 3.4 验证：`build` 分包成功（recharts 独立、页面级 2~20KB lazy chunk），1.7MB 单体消除

## F2 前端健壮性/类型
- [x] 4.1 抽 `hooks/useAsyncData.ts`（统一 loading/error/reload）；3 个详情页（run/用例/pairwise）加 error 兜底渲染 `Result`，消除无限 loading
- [x] 4.2 `main.tsx` 加 `ErrorBoundary`（白屏降级）
- [x] 4.3 定义 `RunDiff`/`RunDiffSide` 类型并应用到 `diffRun` 与看板 diff state（CaseDetail 复杂结构 any 仍由 ESLint 警告跟踪，留 F3 拆分时处理）
- [x] 4.4 验证：`tsc` 0 error + `lint` 0 error + `build` 通过

## B1 后端性能
- [~] 5.1 `load_only` 去 `detail_json`：**搁置**——`_filtered_case_rows` 需读 `detail_json` 派生 n_turns/guideline/trace_url；安全实现需加冗余列+迁移，超出「行为不变」范围，记为后续独立变更
- [x] 5.2 `GET /api/runs` 可选分页（`limit/offset`，缺省返回全部，100% 兼容）
- [x] 5.3 benchmark cases 读盘按 `(storage_path, mtime, profiles)` 缓存 + 深拷贝隔离
- [x] 5.4 复合索引 `ix_case_result_run_sample`/`ix_case_result_run_release`/`ix_case_annotation_run_sample` + `db._ensure_indexes` 幂等补建
- [x] 5.5 验证：`tests/server/test_perf_hardening.py` + 全量 pytest 612 绿

## F3 前端架构
- [x] 6.1 抽 `hooks/useBenchmarkYamlActions`（CaseDetailPage + RunDashboardPage 复用，消除两处 ~50 行重复 try/catch/saving 样板，文案/善后经回调注入保持行为不变）
- [~] 6.2 拆 `RunDashboardPage` / `CaseDetailPage` 子组件、`ConversationThread`/`FilterToolbar`：**建议作为独立变更**——600 行页面拆分触面广、仅收益可维护性，在「行为 100% 不变」前提下风险/收益不对称，单列后续 change 配套快照测试再做
- [x] 6.3 验证：`tsc` 0 error + `lint` 0 error（warning 74→70）+ `build` 通过

## B2 后端整洁/运维
- [x] 7.1 新增 `server/deps.py`：抽出 benchmarks/judge_models 两处完全重复的 `creator_name`（`get_*_or_404` 因各 router 错误文案不同未强行合并，保留以免改变响应文案）
- [x] 7.2 全局 `@app.exception_handler(Exception)`：统一 `{detail}` 错误体 + `logger.exception` 记栈；生产隐藏细节、dev 暴露异常类型
- [x] 7.3 静默 `except: pass`（eval_job 写产物/retention 2 处）+ 残留 `print`（import_history）→ `logging`；新增幂等 `_configure_logging`
- [x] 7.4 `lifespan` finally 调 `JobRunner.shutdown()` 取消在跑评测任务（残留态下次启动 reconcile 回收）+ 启动/关闭结构化日志
- [~] 7.5 补 `response_model`/`summary`：**建议后续独立变更**——现有 dict 返回端点多，补全需逐一核对序列化形状，风险/收益在「行为 100% 不变」前提下不对称
- [x] 7.6 验证：`tests/server/test_robustness_hardening.py` + 全量 server pytest 188 绿

## B3 联调
- [x] 8.1 前端全量改用 `formatApiError`（含 422 验证数组）——F0 已迁移，复查无残留裸 `.data.detail`
- [x] 8.2 修复契约漂移：`RunCreatePayload` 去掉后端不接收的 `tags`、补 `score_profiles?`；`CaseRow` 删除后端 `CaseRowOut` 不存在且前端未读的幻影 `tags`
- [x] 8.3 统一错误提示文案：经 `formatApiError(e, fallback)` 单一信任源，字符串/数组/网络异常归一
- [x] 8.4 验证：前端 `tsc` 0 error

## 收尾
- [ ] 9.1 全量 `pytest` 绿 + 前端 `build` + `medeval run --config config.yaml --dry-run`
- [ ] 9.2 `graphify update .`
- [ ] 9.3 `openspec validate --strict` → `openspec archive`
