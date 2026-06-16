# Proposal: server-backend P1 hardening

## What Changes

- 消除 Service→Router 反向依赖（飞书导出）
- `resume`/`rejudge` 发起下沉 Service，Router 去掉 `session.get`
- 列表 `limit` 默认 50、`le=100`
- 用例列表 `load_only` 排除 `detail_json`
- 任务 `error_msg` 仅存用户可读短句，完整异常进日志

## Non-Goals

- 软删除、benchmark Router 全面收敛、函数拆至 80 行以内
