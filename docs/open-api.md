# MME 评测平台 Open API（v1）

本文用于让外部自动化程序或 AI 发起并跟踪评测任务。

- 生产地址：`https://mme.senzco.com`
- 接口前缀：`/api/open/v1`
- 在线接口文档：`https://mme.senzco.com/docs`
- 返回格式：JSON、UTF-8

> 不要把 API Key 写进代码、聊天记录、日志或 Git 仓库。请通过调用方的环境变量或密钥管理服务注入。

## 1. 使用前准备

平台管理员需在「参数配置 → Open API」创建一把 API Key，并为调用方勾选最小所需权限。一个集成方建议使用一把独立的 Key，以便后续轮换或撤销时不影响其他系统。

所有请求均需携带：

```http
X-MME-API-Key: mme_xxxxxxxxxxxxxxxxx
```

### 权限与接口对应关系

| 权限 | 可调用接口 |
| --- | --- |
| `benchmarks:read` | 查询评测用例集 |
| `judge_models:read` | 查询判分模型 |
| `evaluations:create` | 创建评测任务 |
| `evaluations:read` | 查询单个或批量评测任务结果 |
| `attributions:read` | 查询归因任务的 CX-Agent 优化建议 |

## 2. 推荐调用流程

1. 查询可用 Benchmark，选择 `benchmark_id` 和需要的 `levels`。
2. 如需指定判分模型，查询可用模型并选择 `judge_model_id`。
3. 使用唯一的 `name` 创建评测任务。
4. 保存创建响应中的 `id` 与 `dashboard_url`，按固定间隔轮询任务状态。
5. 当 `status` 为 `success`、`failed` 时停止轮询；可通过 `dashboard_url` 直接打开评测看板。

## 3. 查询可用评测用例集

`GET /api/open/v1/benchmarks`

所需权限：`benchmarks:read`

```bash
curl -sS "$MME_BASE_URL/api/open/v1/benchmarks" \
  -H "X-MME-API-Key: $MME_API_KEY"
```

成功响应：`200 OK`

```json
[
  {
    "id": 19,
    "name": "真实患者数据集benchmark",
    "description": "真实患者场景评测集",
    "version": "v1",
    "case_count": 63,
    "levels": ["L2"],
    "default_evaluation_mode": "single_turn"
  }
]
```

字段说明：

| 字段 | 说明 |
| --- | --- |
| `id` | 创建评测时使用的 `benchmark_id` |
| `levels` | 此用例集实际包含的难度等级 |
| `default_evaluation_mode` | 推荐对话模式；可在创建任务时覆盖 |

## 4. 查询可用判分模型

`GET /api/open/v1/judge-models`

所需权限：`judge_models:read`

```bash
curl -sS "$MME_BASE_URL/api/open/v1/judge-models" \
  -H "X-MME-API-Key: $MME_API_KEY"
```

成功响应：`200 OK`

```json
[
  {
    "id": 1,
    "name": "百炼 DashScope · kimi-k2.6",
    "provider": "openai",
    "model": "kimi-k2.6",
    "has_api_key": true
  }
]
```

只可传入 `has_api_key: true` 的模型 ID。该字段表示模型在当前平台可用：它既包括页面保存的模型密钥，也包括平台服务端安全注入的默认 DashScope 密钥。接口不会返回任何模型密钥。

## 5. 创建评测任务

`POST /api/open/v1/evaluations`

所需权限：`evaluations:create`

请求头：

```http
Content-Type: application/json
X-MME-API-Key: <API_KEY>
```

请求体字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `benchmark_id` | integer | 是 | — | 通过 Benchmark 查询接口取得的 ID |
| `name` | string | 是 | — | 评测名称，1–200 字符，必须全平台唯一。建议包含系统名、日期或流水号 |
| `evaluation_mode` | string | 否 | `single_turn` | `single_turn` 为固定对话；`multi_turn` 为动态多轮对话 |
| `enable_rag` | boolean | 否 | `false` | 是否给被测 CX Agent 启用医学文献 RAG |
| `repeat` | integer | 否 | `1` | 每个用例重复评测次数，必须大于等于 1 |
| `levels` | string[] | 否 | `[]` | 可选值 `L1`、`L2`、`L3`、`L4`；空数组代表评测所有 Level |
| `enable_judge` | boolean | 否 | `true` | 是否启用八维与指南判分 |
| `judge_model_id` | integer/null | 否 | `null` | 已保存的判分模型 ID；留空使用平台默认模型 |

约束：当 `enable_judge` 为 `false` 时，不能传 `judge_model_id`。

```bash
curl -sS -X POST "$MME_BASE_URL/api/open/v1/evaluations" \
  -H "Content-Type: application/json" \
  -H "X-MME-API-Key: $MME_API_KEY" \
  -d '{
    "benchmark_id": 19,
    "name": "my-agent-回归-20260810-001",
    "evaluation_mode": "single_turn",
    "enable_rag": false,
    "repeat": 1,
    "levels": ["L2"],
    "enable_judge": true,
    "judge_model_id": 1
  }'
```

成功响应：`201 Created`

```json
{
  "id": 42,
  "dashboard_url": "https://mme.senzco.com/runs/42",
  "name": "my-agent-回归-20260810-001",
  "status": "pending",
  "benchmark_id": 19,
  "evaluation_mode": "single_turn",
  "repeat": 1,
  "enable_rag": false,
  "enable_judge": true,
  "judge_model_id": 1,
  "result": null,
  "progress": null,
  "queue_position": 1,
  "waiting_for_accounts": false,
  "account_queue": {},
  "error_msg": ""
}
```

`dashboard_url` 是该任务在评测平台中的看板链接，可直接在浏览器打开。`result` 仅在任务成功完成（`status: "success"`）时返回运行结果；排队、运行或失败时固定为 `null`。`queue_position` 表示当前服务内任务队列中的位置；账号资源紧张时，`waiting_for_accounts` 可能为 `true`。这两项均可能为空或随轮询变化，调用方不应据此判断任务失败。

## 6. 查询评测任务状态

`GET /api/open/v1/evaluations/{run_id}`

所需权限：`evaluations:read`

```bash
curl -sS "$MME_BASE_URL/api/open/v1/evaluations/42" \
  -H "X-MME-API-Key: $MME_API_KEY"
```

成功响应：`200 OK`

```json
{
  "id": 42,
  "dashboard_url": "https://mme.senzco.com/runs/42",
  "name": "my-agent-回归-20260810-001",
  "status": "success",
  "benchmark_id": 19,
  "evaluation_mode": "single_turn",
  "repeat": 1,
  "enable_rag": false,
  "enable_judge": true,
  "judge_model_id": 1,
  "result": {
    "total_cases": 63,
    "passed_cases": 48,
    "failed_cases": 15,
    "pass_rate": 0.7619
  },
  "progress": null,
  "queue_position": null,
  "waiting_for_accounts": false,
  "account_queue": {},
  "error_msg": ""
}
```

`result` 字段只有在 `status` 为 `success` 时才有值：

| 字段 | 说明 |
| --- | --- |
| `total_cases` | 本次实际完成评测的用例数 |
| `passed_cases` | 合格用例数 |
| `failed_cases` | 不合格用例数（`total_cases - passed_cases`） |
| `pass_rate` | 通过率，0–1 小数；例如 `0.7619` 表示 76.19% |

当 `status` 为 `pending`、`running` 或 `failed` 时，`result` 均为 `null`。

### 状态含义与轮询建议

| `status` | 含义 | 调用方动作 |
| --- | --- | --- |
| `pending` | 已创建，正在排队或等待账号资源 | 继续轮询 |
| `running` | 正在执行 | 继续轮询 |
| `success` | 评测成功完成 | 停止轮询，到平台查看明细与看板 |
| `failed` | 评测失败 | 停止轮询，读取 `error_msg` 并人工处理 |

建议每 5–15 秒轮询一次。不要并发重复创建同一个业务任务；应先持久化本接口返回的 `id`，用它恢复轮询。

## 7. 按任务类型批量查询评测结果

`GET /api/open/v1/evaluations`

所需权限：`evaluations:read`

用于按评测任务来源批量拉取结果与报告链接。支持的 `trigger_type`：

| 值 | 任务类别 |
| --- | --- |
| `manual` | 人工触发 |
| `scheduled` | 定时任务触发 |
| `open_api` | Open API 触发 |

查询参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `trigger_type` | string | 否 | 全部 | 按任务类别筛选，取值见上表 |
| `status` | string | 否 | 全部 | `pending`、`running`、`success`、`failed` |
| `limit` | integer | 否 | `50` | 每页条数，1–200 |
| `offset` | integer | 否 | `0` | 分页偏移量 |

```bash
curl -sS "$MME_BASE_URL/api/open/v1/evaluations?trigger_type=scheduled&status=success&limit=50" \
  -H "X-MME-API-Key: $MME_API_KEY"
```

成功响应：

```json
{
  "total": 1,
  "items": [
    {
      "id": 58,
      "name": "每日真实患者集回归 · 定时 20260811-093000",
      "status": "success",
      "trigger_type": "scheduled",
      "benchmark_id": 19,
      "dashboard_url": "https://mme.senzco.com/runs/58",
      "created_at": "2026-08-11T01:30:00Z",
      "finished_at": "2026-08-11T01:42:18Z",
      "result": {
        "total_cases": 63,
        "passed_cases": 48,
        "failed_cases": 15,
        "pass_rate": 0.7619,
        "excellent_cases": 18,
        "good_cases": 12,
        "qualified_cases": 18,
        "unqualified_cases": 14,
        "other_cases": 1
      },
      "error_msg": ""
    }
  ]
}
```

每个 `items[]` 都有可直接打开的 `dashboard_url`（评测报告看板链接）。`result` 仅在该评测 `status=success` 时返回，其他状态为 `null`。

结果字段含义：

| 字段 | 说明 |
| --- | --- |
| `excellent_cases` | 评级为“优秀”的用例数量 |
| `good_cases` | 评级为“良好”的用例数量 |
| `qualified_cases` | 评级为“合格”的用例数量 |
| `unqualified_cases` | 评级明确为“不合格”的用例数量 |
| `other_cases` | 没有以上四种最终评级的用例数量，如历史数据缺少评级或执行异常 |
| `failed_cases` | 所有最终未通过的用例数量；它可能包含 `unqualified_cases` 之外的异常未通过用例 |

## 8. 查询归因任务的 CX-Agent 优化建议

`GET /api/open/v1/attribution-tasks`

所需权限：`attributions:read`

该接口用于将已完成或进行中的归因任务提供给外部自动化程序。它**只返回已经确认属于 CX-Agent 的优化建议**：

- 任务级：同类 Case 合并后的 CX-Agent 通用优化点；
- Case 级：该 Case 中有证据支持的扣分项、根因、RAG 诊断与 CX-Agent 优化建议；
- 不返回 Benchmark 判据冲突、判分复核、标注与 RAG 冲突、证据不足等评测工具优化内容。

查询参数：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `run_id` | integer | 否 | 全部 | 仅查询指定评测任务下的归因任务 |
| `status` | string | 否 | 全部 | `queued`、`running`、`success`、`partial`、`failed` |
| `limit` | integer | 否 | `20` | 每页归因任务数，1–50 |
| `offset` | integer | 否 | `0` | 分页偏移量 |

```bash
curl -sS "$MME_BASE_URL/api/open/v1/attribution-tasks?run_id=35&status=success" \
  -H "X-MME-API-Key: $MME_API_KEY"
```

成功响应：

```json
{
  "total": 1,
  "items": [
    {
      "id": 5,
      "run_id": 35,
      "run_name": "真实患者集回归",
      "report_url": "https://mme.senzco.com/runs/35/attribution-tasks/5",
      "status": "success",
      "total_count": 23,
      "completed_count": 23,
      "success_count": 23,
      "failed_count": 0,
      "cx_agent_optimization_summary": {
        "cx_agent_case_count": 23,
        "clusters": [
          {
            "cause_label": "召回证据未用于回答",
            "dimensions": ["专业准确性与边界"],
            "case_count": 4,
            "priority": "P1",
            "recommendations": [
              {
                "target": "提示词优化",
                "action": "生成回答前逐条核对选中文献"
              }
            ]
          }
        ]
      },
      "cases": [
        {
          "sample_id": "case_12",
          "scenario": "升白片用药",
          "case_type": "用药方法与药物安全",
          "status": "success",
          "cx_agent_optimization": {
            "summary": "回答未使用已召回的关键风险证据",
            "deductions": [
              {
                "deduction_id": "guideline.g02",
                "dimension": "professional_accuracy",
                "finding": "已召回证据但回答没有引用",
                "primary_cause": {"label": "召回证据未用于回答", "owner": "generator"},
                "recommendations": [{"target": "提示词优化", "action": "增加文献覆盖检查"}]
              }
            ],
            "recommendations": []
          }
        }
      ]
    }
  ]
}
```

`report_url` 可直接打开该归因任务的详情页。任务正在执行时，已完成 Case 会立即出现在 `cases` 中；尚未完成、失败或评测侧需要复核的 Case，其 `cx_agent_optimization.deductions` 会为空。

## 9. Python 调用模板

```python
import os
import time
import requests

base_url = os.environ.get("MME_BASE_URL", "https://mme.senzco.com")
headers = {"X-MME-API-Key": os.environ["MME_API_KEY"]}

# 1) 发现资源
benchmarks = requests.get(f"{base_url}/api/open/v1/benchmarks", headers=headers, timeout=30)
benchmarks.raise_for_status()
benchmark = benchmarks.json()[0]

models = requests.get(f"{base_url}/api/open/v1/judge-models", headers=headers, timeout=30)
models.raise_for_status()
judge_model = next(item for item in models.json() if item["has_api_key"])

# 2) 创建任务：name 必须唯一
payload = {
    "benchmark_id": benchmark["id"],
    "name": "my-agent-回归-20260810-001",
    "evaluation_mode": benchmark["default_evaluation_mode"],
    "enable_rag": False,
    "repeat": 1,
    "levels": benchmark["levels"],
    "enable_judge": True,
    "judge_model_id": judge_model["id"],
}
created = requests.post(
    f"{base_url}/api/open/v1/evaluations",
    headers={**headers, "Content-Type": "application/json"},
    json=payload,
    timeout=30,
)
created.raise_for_status()
run = created.json()

# 3) 轮询至结束
while run["status"] in {"pending", "running"}:
    time.sleep(10)
    status = requests.get(
        f"{base_url}/api/open/v1/evaluations/{run['id']}",
        headers=headers,
        timeout=30,
    )
    status.raise_for_status()
    run = status.json()

if run["status"] != "success":
    raise RuntimeError(run.get("error_msg") or f"评测失败：{run}")

print(f"评测完成，run_id={run['id']}，看板：{run['dashboard_url']}")
```

## 10. 错误码

| 状态码 | 说明 | 常见处理方式 |
| --- | --- | --- |
| `401` | 未提供 `X-MME-API-Key` | 检查请求头 |
| `403` | Key 无效、已轮换/删除，或没有该接口权限 | 使用正确 Key 或请管理员补充权限 |
| `404` | `run_id` 不存在 | 核对任务 ID |
| `409` | 评测名称重复 | 更换为新的唯一 `name`；不要无脑重试创建 |
| `422` | 请求字段缺失、格式错误或参数组合不合法 | 根据响应 `detail` 修正请求体 |
| `503` | 平台尚未创建可用 API Key | 请平台管理员在「Open API」页签创建并授权 |
| `5xx` | 平台暂时异常 | 使用指数退避重试查询；创建任务前先确认是否已创建成功，避免重复任务 |

## 11. 给 AI 调用方的约束

1. 只能调用本文列出的 `/api/open/v1` 接口，不要尝试调用平台后台管理接口。
2. API Key 只能从安全环境变量读取，绝不在回复中输出其完整值。
3. 创建任务前先查询 Benchmark；不得臆造 `benchmark_id`、`judge_model_id` 或 Level。
4. `name` 必须生成唯一值，例如 `<系统名>-<用途>-<UTC时间戳>`；保存返回的 `run_id` 与 `dashboard_url`。
5. 调用方应持久化「业务任务 → 唯一名称 → `run_id`」的映射。创建请求超时或网络中断时，不要直接再次创建；先通过已保存的 `run_id` 继续轮询，或请平台管理员在评测列表按名称确认，避免重复任务消耗评测账号。
6. 仅在 `status` 为 `success` 时报告评测成功；`pending` 与 `running` 都不代表失败。
