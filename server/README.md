# MME 评测平台后端

FastAPI 后端负责 Benchmark v2 管理、评测任务执行、结果持久化和前端 API。

## 当前评分数据

平台只处理新评分结构：

- `medical_safety_passed`
- `dimension_raw_scores`
- `guideline_scores`
- `dimension_scores`
- `end_scores`
- `composite_score`（0～40）
- `grade`
- `release_passed`

Benchmark 的可编辑判据只有 `evaluation.dimension_criteria` 和 `evaluation.guidelines`。上传及保存都会经过严格的 `TestCase` v2 校验。

## 启动

```bash
pip install -e '.[server]'
uvicorn server.app:app --reload
```

默认开发数据库为 SQLite；部署参数见 `server/settings.py`。启动时会建表并回收进程重启前遗留的运行中任务。

## 主要接口

- `/api/health`：健康检查
- `/api/benchmarks`：Benchmark 管理
- `/api/runs`：评测任务和 Case 结果
- `/api/runs/{run_id}/cases/{sample_id}/agent-chain/sync`：重新同步该 Case 的 cx-agent Langfuse 调用链
- `/api/config/evaluation-standard`：八维、三端、评级和指南扣分公式
- `/api/judge-models`：Judge 模型连接配置

生产环境可托管 `frontend/dist`。开发环境通常使用 Vite dev server 代理 API。

当 `config.yaml` 的 `adapter.cx_agent.isolated_accounts=true` 时，每个 Case 会在开始前领取并清空一个 cx-agent 专用测试账号，多轮对话复用该账号，结束后释放。配置 `LANGFUSE_HOST`、`LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY` 后，评测结果会保存每轮 Agent/Generation/Tool 调用链快照；未配置时评测仍可完成，Case 明细会显示“Langfuse 读取尚未配置”。
