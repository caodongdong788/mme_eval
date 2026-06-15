# Proposal: 判分模型配置中心 + 发起评测下拉选模型（含详情页回退优化）

## Why

两点优化：
1. 用例详情页「← 返回看板」回退到看板「概览」，但用户来自「用例明细」列表，期望回退到用例列表（明细 tab）。
2. 发起评测时每次都要手填打分模型（provider/model/base_url/api_version/api_key），重复且易错，API Key 还要反复输入。
   应在「资源」下新增「判分模型」配置中心：一次配好连接信息（含 Key），发起评测时直接下拉选用，免手填。

## What Changes

- 用例详情页回退 MUST 落到看板「用例明细」tab（看板 tab MUST 随选择记忆）。
- 新增「判分模型配置」实体与 CRUD：
  - 后端 MUST 新增 `judge_model_config` 表（name 唯一、provider/model/base_url/api_version/temperature/api_key/created_by）。
  - 新增 `GET/POST/PATCH/DELETE /api/judge-models`。**全局共享**（所有登录用户可见可用）。
  - API Key MUST 落库但**只写不读**：列表/详情接口只回 `has_api_key` 掩码标记，绝不明文返回；发起评测时由后端读取注入，Key 不经前端回传。
- 发起评测 `POST /api/runs` MUST 支持 `judge_model_id`：选中后由后端据该配置构建 judge 覆盖（连接信息 + Key），不选则沿用服务器 `config.yaml` 默认。
- 前端「资源」菜单 MUST 新增「判分模型」配置页（增删改、Key 写入/掩码展示）；发起评测页打分模型区 MUST 改为下拉选择（不再手填连接信息）。

## Impact

- Affected specs: `eval-platform-dashboard`（新增「判分模型配置」能力 + 详情页回退、发起评测选模型）。
- Affected code:
  - 后端：`server/models_db.py`（新表）、`server/schemas.py`（JudgeModel* + `RunCreate.judge_model_id`）、
    `server/routers/judge_models.py`（新 CRUD）、`server/app.py`（注册）、`server/routers/runs.py`（注入）。
  - 前端：`api.ts`（类型/方法）、新页 `JudgeModelsPage.tsx`、`App.tsx`（菜单/路由）、`LaunchPage.tsx`（下拉）、
    `RunDashboardPage.tsx` + `CaseDetailPage.tsx`（回退 tab）。
- 判分内核 `medeval/**` 零改动（仍走既有 judge override 合并路径）。新表由 `create_all` 自动建，无需手写迁移。

## 安全说明

API Key 落库属本平台内部评测工具的有意取舍：库内明文存储、接口侧只写不读（响应仅 `has_api_key`），
发起评测时服务端读取注入运行期、不写入 run 的 `judge_overrides`（仍走 `public_dict` 剔除 Key）。
