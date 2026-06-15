## Why

人审「推翻机器」后想改判据，目前唯一通路是离开用例明细页、跳到看板「编辑判据(YAML)」按过滤子集整包编辑，再手动选 benchmark 重判——跨页、粒度粗、改前无法验证一条判据是否真能得到期望判定。需要让审核者在**用例明细页就地**改这一条用例的判据、**先单条试判预览验证**、满意后再**覆盖回这次评测当前的 benchmark**，形成紧凑闭环。

## What Changes

- 新增**单用例 ephemeral 试判预览**能力：在用例明细页带编辑后的判据触发，复用冻结 trace 与 `judge_traces` 只重判这一条，返回新 verdict / 四维分 / 上线判定及与当前值的 diff；**不落库、不产新 run、不回写当前 run、不碰 HITL 旁路**（方案 A）。
- 用例明细页 HITL 卡片的「去改判据(YAML)」从跳看板改为**就地打开现有 `EditCriteriaDrawer`**，且**只装当前 `sample_id` 这一条**用例的判据 YAML；满意后复用现成「覆盖当前 benchmark」覆盖这次评测当前关联的 benchmark。
- 编辑判据 YAML 时**显式展示当前 benchmark 名称**（抽屉内可见 `#id「名称」`），避免覆盖错对象。
- 后端 `cases-yaml` 导出端点支持按 `sample_id` 过滤，便于只取单条用例 YAML 预填编辑器。

## Capabilities

### New Capabilities
<!-- 无新增能力，复用并扩展现有平台能力 -->

### Modified Capabilities
- `eval-platform-service`: 新增「单用例 ephemeral 试判预览端点」需求；扩展「导出过滤用例的完整 YAML 供在线编辑」需求以支持按 `sample_id` 过滤。
- `eval-platform-dashboard`: 新增「用例明细页就地编辑判据并单条试判预览」需求；扩展判据编辑界面在编辑时展示当前 benchmark 名称。

## Impact

- 后端 `server/routers/runs.py`：新增 `POST /api/runs/{run_id}/cases/{sample_id}/preview-rejudge`；扩展 `GET /api/runs/{run_id}/cases-yaml` 支持 `sample_id` 过滤。
- 后端 `server/eval_job.py` / `server/schemas.py`：复用 `_frozen_cases_and_traces` + `judge_traces` + `score_case` 构造单条 ephemeral 试判，新增 preview 请求/响应 schema；不新增 ORM 列、不产生 run。
- 前端 `frontend/src/pages/CaseDetailPage.tsx`：HITL 卡片就地打开 `EditCriteriaDrawer` + 试判预览 UI + diff 展示。
- 前端 `frontend/src/components/EditCriteriaDrawer.tsx`：展示当前 benchmark 名称（新增展示属性）。
- 前端 `frontend/src/api.ts`：新增 `previewRejudgeCase`，扩展 `getRunCasesYaml` 过滤参数。
- 判分内核 `medeval/**`：不改核心节点（`TestCase` / `BaseJudge` / `FailureTag` 不动），仅复用 `judge_traces` / `score_case`。
