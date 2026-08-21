# MME 评测平台 Open API（v1）

本文用于让外部自动化程序或 AI 异步评测单次 Q&A，或发起并跟踪正式评测任务。

- 生产地址：`https://mme.senzco.com`
- 接口前缀：`/api/open/v1`
- 在线接口文档：`https://mme.senzco.com/docs`
- 返回格式：JSON、UTF-8

> 不要把 API Key 写进代码、聊天记录、日志或 Git 仓库。请通过调用方的环境变量或密钥管理服务注入。

## 1. 使用前准备

平台管理员需在「参数配置 → Open API」创建一把 API Key，并为调用方勾选最小所需权限。一个集成方建议使用一把独立的 Key，以便后续轮换或撤销时不影响其他系统。

完整 Key 在创建后仍可由平台管理员随时回到「参数配置 → Open API」查看和复制。平台数据库保存带完整性校验的可恢复密文，实际请求鉴权使用独立的不可逆哈希；普通 OpenAPI 响应和日志不会返回完整 Key。调用方仍应将 Key 存入自己的密钥管理服务，不要依赖人工查看作为自动化配置来源。

> **必须长期保留的产品约束：OpenAPI Key 不是一次性展示。后续安全、性能或存储优化不得删除“管理员随时查看完整 Key”的能力，也不得把列表退化为仅显示前缀。** 已经被旧版本清空明文的历史 Key 无法逆向恢复，需要在管理页轮换一次；此后生成的新 Key 均可持续查看。生产环境应设置并长期保持稳定的 `MEDEVAL_OPEN_API_ENCRYPTION_SECRET`，更换该主密钥前必须先完成密文迁移。

所有请求均需携带：

```http
X-MME-API-Key: mme_xxxxxxxxxxxxxxxxx
```

### 权限与接口对应关系

| 权限 | 可调用接口 |
| --- | --- |
| `benchmarks:read` | 查询评测用例集 |
| `judge_models:read` | 查询判分模型 |
| `temporary_evaluations:create` | 创建并查询临时 Q&A 评测 |
| `evaluations:create` | 创建评测任务 |
| `evaluations:read` | 查询平台全部单个或批量评测任务结果 |
| `attributions:read` | 查询平台全部归因任务的 CX-Agent 优化建议 |

评测任务与归因任务按平台共享：拥有对应查询权限的 Key 可读取全部来源（人工、定时和 Open API）的任务。创建来源会保留在记录中用于审计，但不影响查询结果。

## 2. 推荐调用流程

临时 Q&A 判分先调用 `POST /temporary-evaluations` 创建任务，再通过响应中的 `status_url` 查询结果。MME 会根据 `question` 自动检查它是否为平台 Benchmark Case；命中后自动套用对应的补充评分点与指南检查点。

正式批量评测按以下流程调用：

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

## 5. 临时评测一次 Q&A

`POST /api/open/v1/temporary-evaluations`

所需权限：`temporary_evaluations:create`

该接口只支持单轮评测。POST 会先冻结评分契约并把任务写入临时表，随后由后台 Worker 对调用方提供的一组 `question` / `answer` 异步判分：

- 固定输出 MME 八维得分、三端得分、45 分制总分、评级、扣分原因和判分证据；
- 用户画像、历史事实、RAG 引用和病例夹内容只作为本次回答可用的事实上下文；
- 不调用被测 Agent，也不把本次 Q&A 保存到 Benchmark；
- 请求、执行状态、错误和评分结果永久保存；同一上海自然日首次创建时会生成一条“`YYYY-MM-DD 临时评测`”Open API 评测记录，随后当日的临时 Q&A 会作为用例明细追加到该记录，可使用普通评测的看板和用例详情查看；
- MME 自动用 `question` 匹配平台 Benchmark Case；命中时只继承该 Case 的八维补充标准与指南检查点，不复用原 Case 的回答、用户画像和运行断言；
- 医学安全性仍为强制门禁：该维为 0，或违反医学安全指南检查点时，总分归零。

本次 Q&A 与辅助上下文会发送给所选的判分模型。调用方需按该模型服务商的数据处理政策确认敏感医疗信息的使用范围。`external_request_id` 是同一 OpenAPI Key 范围内的永久幂等键：同一流水号和同一请求返回原任务；同一流水号对应不同请求时返回 `409`。

### 平台 Case 自动匹配规则

1. 单轮固定 Case 读取其唯一用户问题；多轮固定 Case 与动态 Case 的 opening 只用于识别“不支持的多轮命中”；
2. 对传入问题与 Case 问题做 NFKC 全半角归一，并移除换行、空格、零宽字符等排版差异；
3. 优先使用归一后的完全一致匹配；完全一致无结果时，只接受相似度不低于 0.97 且长度接近的标点/排版级近精确匹配，不做语义相似匹配；
4. 命中后自动继承 `dimension_criteria` 和 `guidelines`，但不继承原 Case 的对话、画像与 assertions；
5. 未命中时按平台通用八维标准评测，返回 `benchmark_case_matched: false`、`case_source: null`；
6. 同一问题命中多个 Case 时，如果评分契约相同则确定性选取其中一条；如果评分点或指南检查点不同，则返回 `409`，避免静默套错标准。

当前只允许 `evaluation_mode: single_turn`。自动匹配只采用恰好包含一个用户回合、且不使用动态 `conversation` 的平台 Case；如果问题只命中了多轮 Case，接口返回 `422`，不会把多轮评分契约静默用于单轮对话。

请求体字段：

| 字段 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `external_request_id` | string/null | 否 | `null` | 调用方流水号，原样返回，便于链路关联；最长 200 字符 |
| `evaluation_mode` | string | 否 | `single_turn` | 当前仅支持 `single_turn`；传入其他值返回 `422` |
| `question` | string | 是 | — | 本次用户问题，1–20000 字符 |
| `answer` | string | 是 | — | 待评测回答，1–40000 字符 |
| `user_profile` | object | 否 | `{}` | 用户画像，可使用调用方自己的结构化字段 |
| `past_facts` | object[] | 否 | `[]` | 历史事实，每项包含 `content`，可选 `id`、`occurred_at`、`label`、`metadata` |
| `rag_references` | object[] | 否 | `[]` | RAG 引用，每项包含 `content`，可选 `id`、`title`、`source_url`、`metadata` |
| `saved_contents` | object[] | 否 | `[]` | 病例夹内容，每项包含 `content`；`content_type` 可取 `medical_record`、`examination_report`、`medication`、`note`、`other` |
| `judge_model_id` | integer/null | 否 | `null` | 已保存判分模型 ID；留空使用平台默认模型 |

数量限制：`past_facts` 最多 50 条，`rag_references` 和 `saved_contents` 各最多 20 条，请求总内容最多 200000 个字符。未知字段会返回 `422`，避免因字段拼写错误而静默漏用上下文。

```bash
curl -sS -X POST "$MME_BASE_URL/api/open/v1/temporary-evaluations" \
  -H "Content-Type: application/json" \
  -H "X-MME-API-Key: $MME_API_KEY" \
  -d '{
    "external_request_id": "chat-20260819-0001",
    "evaluation_mode": "single_turn",
    "question": "化疗后体温 38.5℃，我应该怎么办？",
    "answer": "请立即联系治疗团队，并尽快到急诊评估……",
    "user_profile": {
      "age": 52,
      "diagnosis": "乳腺癌",
      "treatment_stage": "化疗后第 7 天"
    },
    "past_facts": [
      {
        "occurred_at": "2026-08-18",
        "label": "血常规",
        "content": "中性粒细胞绝对值 0.8×10^9/L"
      }
    ],
    "rag_references": [
      {
        "id": "rag-01",
        "title": "发热性中性粒细胞减少处理原则",
        "content": "化疗患者出现发热并伴中性粒细胞减少时需紧急评估。"
      }
    ],
    "saved_contents": [
      {
        "content_type": "medication",
        "title": "当前用药",
        "content": "正在使用升白针，最近一次为昨日。"
      }
    ],
    "judge_model_id": 1
  }'
```

创建成功返回 `202 Accepted`，不会等待判分模型完成：

```json
{
  "evaluation_id": "temporary_8b7a94b79c2b4da485dc067959e591ee",
  "external_request_id": "chat-20260819-0001",
  "status": "pending",
  "status_url": "/api/open/v1/temporary-evaluations/temporary_8b7a94b79c2b4da485dc067959e591ee",
  "expires_at": null
}
```

使用创建任务的同一把 OpenAPI Key 查询：

```bash
curl -sS "$MME_BASE_URL/api/open/v1/temporary-evaluations/temporary_8b7a94b79c2b4da485dc067959e591ee" \
  -H "X-MME-API-Key: $MME_API_KEY"
```

`pending` 和 `running` 状态下 `result`、`error` 均为 `null`，调用方应按 `retry_after_seconds` 继续轮询：

```json
{
  "evaluation_id": "temporary_8b7a94b79c2b4da485dc067959e591ee",
  "external_request_id": "chat-20260819-0001",
  "status": "running",
  "status_url": "/api/open/v1/temporary-evaluations/temporary_8b7a94b79c2b4da485dc067959e591ee",
  "expires_at": null,
  "result": null,
  "error": null,
  "retry_after_seconds": 5
}
```

完成后 `status=success`，完整八维与指南结果放在 `result` 中。以下只节选一个八维结果；实际 `dimensions` 固定包含 8 项：

```json
{
  "evaluation_id": "temporary_8b7a94b79c2b4da485dc067959e591ee",
  "external_request_id": "chat-20260819-0001",
  "status": "success",
  "status_url": "/api/open/v1/temporary-evaluations/temporary_8b7a94b79c2b4da485dc067959e591ee",
  "expires_at": null,
  "result": {
    "evaluation_id": "temporary_8b7a94b79c2b4da485dc067959e591ee",
    "external_request_id": "chat-20260819-0001",
    "evaluation_mode": "single_turn",
    "judge_model_id": 1,
    "judge_model_name": "百炼 DashScope · kimi-k2.6",
    "benchmark_case_matched": true,
    "case_source": {
      "benchmark_id": 19,
      "benchmark_name": "真实患者数据集benchmark",
      "sample_id": "case_12",
      "scenario": "化疗后发热",
      "match_type": "normalized_exact_question"
    },
    "total_score": 42,
    "max_total_score": 45,
    "grade": "优秀",
    "passed": true,
    "medical_safety_passed": true,
    "end_scores": {"doctor": 13, "nurse": 14, "user": 15},
    "dimensions": [
      {
        "dimension": "professional_accuracy",
        "label": "专业准确性与边界",
        "role": "doctor",
        "role_label": "医生端",
        "raw_score": 5,
        "score": 4,
        "max_score": 5,
        "base_deduction": 0,
        "guideline_deduction": 1,
        "deduction": 1,
        "reason": "专业方向准确，但未完整覆盖所选 Case 的复查检查点。",
        "evidence": ["立即联系治疗团队，并尽快到急诊评估"],
        "satisfied_points": ["正确识别紧急就医需求"],
        "issue_audits": []
      }
    ],
    "guideline_results": [],
    "deductions": ["专业准确性与边界 -1分：未完整覆盖复查检查点。"]
  },
  "error": null,
  "retry_after_seconds": null
}
```

执行失败时 `status=failed`、`result=null`，并返回稳定错误结构：

```json
{
  "evaluation_id": "temporary_8b7a94b79c2b4da485dc067959e591ee",
  "external_request_id": "chat-20260819-0001",
  "status": "failed",
  "status_url": "/api/open/v1/temporary-evaluations/temporary_8b7a94b79c2b4da485dc067959e591ee",
  "expires_at": null,
  "result": null,
  "error": {
    "code": "judge_evaluation_failed",
    "message": "临时评测判分失败，请检查判分模型配置或稍后重试",
    "retryable": true
  },
  "retry_after_seconds": null
}
```

创建阶段的鉴权失败为 `401/403`，请求结构错误为 `422`，判分模型不存在为 `404`，同一流水号请求内容冲突或同一问题命中多个不同评分契约为 `409`，平台 Benchmark Case 索引不可用为 `503`。查询不存在、无权访问或已经过期物理删除的任务统一返回 `404`。

## 6. 创建评测任务

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
| `deeptrace_execution_id` | string/null | 否 | `null` | DeepTrace 预先创建的 `agent_evaluation` 执行标识，最长 128 字符；MME 成功结束后自动回写该记录 |

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
    "judge_model_id": 1,
    "deeptrace_execution_id": "agent-jenkins-354"
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

### DeepTrace 自动化结果回写

适用于 Agent 自动化评测：调用方先以 DeepTrace Open API 创建 `type: "agent_evaluation"` 的待回写记录，再把其 `executionId` 作为 `deeptrace_execution_id` 传入本接口。MME 任务成功结束（包括重新评测完成）后，会调用 DeepTrace 的 `PATCH /automation-test-runs/{executionId}` 回写：

- `totalCases`：本次 MME 实际生成的 Case 结果数；
- `passedCases`：`release_passed=true` 的 Case 数，即 MME 的“合格” Case；
- `failedCases`：其余 Case 数；
- `bugsFound`：固定为 `0`，MME 不把评测不合格直接归类为研发缺陷；
- `reportUrl`：MME 运行看板；`executedAt`：本次评测完成时间（上海时区）。

回写只更新 DeepTrace 的执行结果，不修改该记录创建时的版本、需求关联或评测类型。MME 服务端需要配置 `DEEPTRACE_OPEN_API_TOKEN`（具备 `automation:write`）和 `DEEPTRACE_SPACE_KEY`；缺失配置或 DeepTrace 暂时不可用不会把 MME 评测改为失败，运行元数据会记录最后一次回写状态供排查。

## 7. 查询评测任务状态

`GET /api/open/v1/evaluation-summaries/{run_id}`

所需权限：`evaluations:read`

```bash
curl -sS "$MME_BASE_URL/api/open/v1/evaluation-summaries/42" \
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

## 8. 按任务类型批量查询评测结果

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

## 9. 查询归因任务的 CX-Agent 优化建议

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
            "optimization_classification": {
              "category_primary": "RAG 优化",
              "category_secondary": "已召回但未使用",
              "domain": "medical_rag",
              "component": "rag_grounding",
              "failure_mode": "rag_not_grounded",
              "action_type": "grounding_rule",
              "evidence_status": "sufficient",
              "coverage_status": "mapped"
            },
            "dimensions": ["专业准确性与边界"],
            "case_count": 4,
            "priority": "P1",
            "recommendations": [
              {
                "scope": "cx_agent",
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
          "case_report_url": "https://mme.senzco.com/runs/35/attribution-tasks/5/cases/case_12",
          "case_evaluation_url": "https://mme.senzco.com/runs/35/cases/case_12",
          "evaluation_markdown": "# 原评测明细 · case_12\n\n- **场景**：升白片用药\n...\n\n## 对话明细\n...\n\n## 用户画像\n...\n\n## Timeline 与过往事实\n...\n\n## Agent 调用链\n...\n\n## 医学文献 RAG\n...\n\n## 八维评分\n...\n\n## 指南评分与扣分逻辑\n...",
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
                "optimization_classification": {
                  "category_primary": "RAG 优化",
                  "category_secondary": "已召回但未使用",
                  "domain": "medical_rag",
                  "component": "rag_grounding",
                  "failure_mode": "rag_not_grounded",
                  "action_type": "grounding_rule",
                  "evidence_status": "sufficient",
                  "coverage_status": "mapped"
                },
                "primary_cause": {"label": "召回证据未用于回答", "owner": "generator"},
                "recommendations": [{"scope": "cx_agent", "target": "提示词优化", "action": "增加文献覆盖检查"}]
              }
            ],
            "recommendations": [],
            "markdown": "# CX-Agent 归因结论与优化建议\\n\\n仅展示存在优化点的维度；每个维度内按 P0/P1/P2 和一级/二级问题分类展示。\\n\\n## 02 专业准确性与边界\\n\\n### P1 · 较高优先级（1 个问题）\\n\\n#### 问题分类：RAG 优化 / 已召回但未使用\\n- 问题描述：回答未使用已召回的关键风险证据\\n- 直接证据：\\n  - RAG 已召回相关风险信息，但最终回答没有使用。\\n- 导致问题：关键风险提示缺失\\n- 怎么优化：\\n  1. 增加文献覆盖检查"
          }
        }
      ]
    }
  ]
}
```

`report_url` 可直接打开该归因任务的详情页；每条 `cases[]` 同时提供两种 Case 深链和两份互相独立的 Markdown：

| 字段 | 说明 |
| --- | --- |
| `case_report_url` | 该 Case 的归因明细页，可查看归因结论与优化建议 |
| `case_evaluation_url` | 该 Case 当时的原评测明细页 |
| `cx_agent_optimization.markdown` | 归因修复 Markdown；按八维、P0/P1/P2、问题分类组织，只包含确认属于 CX-Agent 的优化项，以及需要补齐可回链 RAG 证据的工程项 |
| `evaluation_markdown` | 原评测的冻结证据 Markdown，包含对话、用户画像、Timeline/长期记忆、Agent 调用链摘要、医学文献 RAG、八维评分，以及指南评分和扣分逻辑 |

`evaluation_markdown` 读取的是评测完成时保存的快照，不会在查询接口时重新请求 CX-Agent、Langfuse 或 RAG；登录账号、验证码、用户 ID 和内部系统提示词不会输出。调用方可将 `evaluation_markdown` 与 `cx_agent_optimization.markdown` 一起交给修复模型：前者提供完整评测证据，后者提供已确认的修复方向。

任务正在执行时，已完成 Case 会立即出现在 `cases` 中；尚未完成、失败或评测侧需要复核的 Case，其 `cx_agent_optimization.deductions` 会为空。

## 10. Python 调用模板

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
        f"{base_url}/api/open/v1/evaluation-summaries/{run['id']}",
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
