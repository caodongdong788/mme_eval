## Why

一次全面代码审计发现平台前后端存在一批**与判分业务无关**的工程债：前端无 ESLint、路由未懒加载（单体 1.7MB）、取数失败会无限 loading、核心类型为 `any`、大页面与重复逻辑；后端胖路由、列表全列加载 `detail_json`、无分页、产物路径有穿越面、弱默认 `SESSION_SECRET`、上传无上限、无全局异常处理与优雅关闭。本变更在**保证现有功能与判分行为 100% 不变**的前提下，分批重构结构、性能、安全、规范。

## What Changes

分批推进（低风险→高风险），每批先补测试再改：

- **F0 前端工程化**：接入 ESLint/Prettier；删死代码（`passColor` 等）；抽 `labels.ts`（DIM/PROFILE/STABILITY）、`utils/apiError.ts`（`formatApiError`）；axios 加 `timeout` 与请求拦截器；修复 `theme.ts`↔`styles.css` 的 `chart.ink` token 镜像偏差。
- **F1 前端性能**：路由 `React.lazy`+`Suspense` 懒加载；Vite `manualChunks` 拆 vendor；轮询改为「有进行中任务才轮询」+ 页面不可见暂停。
- **F2 前端健壮性/类型**：抽 `useAsyncData` 统一 loading/error 兜底（消除无限 loading）；加 `ErrorBoundary`；核心 `any`→`CaseDetail`/`RunDiff` 类型。
- **F3 前端架构**：拆 `RunDashboardPage`/`CaseDetailPage`；抽 `ConversationThread`、`useBenchmarkYamlActions`。
- **B0 后端安全**：`run_slug` 白名单 + 产物路径统一 `safe_join` 边界校验；生产强制非默认 `SESSION_SECRET`（否则启动失败）+ HTTPS 下 cookie `Secure`；benchmark 上传大小上限；写类接口统一登录校验。**不含资源级授权/租户隔离**（保持现有可见性）。
- **B1 后端性能**：列表查询 `load_only` 排除大字段 `detail_json`；`GET /api/runs` 可选分页（高默认上限、不破坏现有调用）；benchmark cases 读盘按 `mtime` 缓存；高频过滤列加复合索引（ORM 幂等补列）。
- **B2 后端整洁/运维**：抽 `deps.py`（统一 `_get_*_or_404`/`_creator_name`）+ `CaseFilterParams` 过滤模型；注册全局 `exception_handler` 统一错误体；静默 `except: pass`/残留 `print` 改 `logging`；`lifespan` 增加 shutdown 优雅收尾后台任务；补缺失 `response_model` 与 OpenAPI `summary`。
- **B3 联调**：前端 `formatApiError` 处理 422 数组 `detail`；修复契约漂移（`tags`/`score_profiles`、`CaseRow.tags`）；统一错误提示文案。

## Capabilities

### New Capabilities
<!-- 无新增能力 -->

### Modified Capabilities
- `eval-platform-service`: 新增产物路径边界安全、上传大小上限、生产 SESSION_SECRET 强校验、列表分页、全局异常处理与优雅关闭等防御性/运维性需求（不改判分行为）。
- `eval-platform-dashboard`: 新增取数失败的错误兜底状态（不再无限 loading）需求；其余前端为非行为性重构。

## Impact

- 前端：`frontend/`（新增 eslint 配置、`hooks/`、`utils/`、`labels.ts`）、`App.tsx`、`vite.config.ts`、`api.ts`、`theme.ts`、`styles.css`、`pages/*`、`components/*`。
- 后端：`server/app.py`、`settings.py`、`auth.py`、`routers/*`、`benchmarks.py`、`eval_job.py`、`models_db.py`、新增 `server/deps.py`、`medeval/run_slug.py`（仅加路径消毒，不改 slug 业务语义）。
- 测试：每批补 `tests/`（路径安全、上传上限、分页、load_only、formatApiError 等）。
- 不改判分内核业务逻辑（`judges/`、`reporter/scoring` 等），不改 `TestCase`/`BaseJudge`/`FailureTag`。
