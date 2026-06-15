# eval-platform-service Specification (delta)

## ADDED Requirements

### Requirement: 启动回收孤儿评测任务

评测任务由进程内调度执行，状态仅存于内存。系统启动时 SHALL 回收"孤儿任务"：凡 `eval_run.status`
为 `running` 或 `pending` 的记录 MUST 被标记为 `failed`，并写入可读的 `error_msg` 说明因服务重启
中断，且补齐 `finished_at`。回收 MUST 仅影响 running/pending 记录，对 `success`/`failed` 记录无副作用，
且重复执行幂等。回收后的记录因不再处于 running/pending，MUST 可被删除。

#### Scenario: 重启后回收卡住的任务

- **WHEN** 进程重启时 DB 中存在 status 为 running 或 pending 的 run
- **THEN** 启动回收 MUST 将其置为 failed 并写入中断说明，使其可被删除；success 记录 MUST 保持不变
