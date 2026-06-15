# Proposal: 启动回收孤儿评测任务

## Why

评测任务由进程内 `InProcessJobRunner`（asyncio）执行，状态机仅活在内存。进程重启（含 `uvicorn --reload`
热重载、Cursor/IDE 重启、崩溃）会杀掉正在跑的 asyncio 任务，但 DB 里的 `eval_run.status` 仍停在
`running`/`pending`。这类"孤儿任务"：
- 删除被守卫拦截（运行中/等待中不可删除）；
- 续跑被守卫拦截（运行中/等待中不可续跑）；
- 永远不会完成。

用户重启 Cursor 后，run #7 卡在"运行中"，既删不掉也续不了。需要在启动时把不可能再存活的
running/pending 任务回收为失败态，让其可删、可重新发起。

## What Changes

- 新增**启动回收**：应用启动（lifespan）建表后，凡 `status ∈ {running, pending}` 的 run MUST 被标记为
  `failed`，写入可读 `error_msg`（如"服务重启导致任务中断"），并补 `finished_at`。新进程启动时不存在
  任何在跑任务，故此回收安全且必要。
- 回收后这些 run 不再处于 running/pending，因而 MUST 可被删除；用户可删除后重新发起评测。

## Impact

- Affected specs: `eval-platform-service`（任务生命周期/孤儿回收）。
- Affected code: `server/jobs.py`（回收函数）、`server/app.py`（lifespan 调用）；
  测试 `tests/server/test_orphan_recovery.py`。
- 判分内核 `medeval/**` 零改动。
