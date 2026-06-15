## MODIFIED Requirements

### Requirement: 评测任务调度与状态跟踪

系统 SHALL 通过 `JobRunner` 抽象异步执行评测：发起后立即创建 `eval_run(status=pending)` 并返回 run id，后台执行时状态流转 `pending → running → success/failed`，失败 MUST 记录 `error_msg`。多个评测任务并发执行 MUST 受并发上限约束。运行进度 SHALL 可被查询，且其完成百分比 MUST 为「跨全部阶段的全局累计值」、随评测推进**单调不回退**（一次评测含多个顺序阶段时，切换阶段 MUST NOT 使百分比下降）。

#### Scenario: 发起评测立即返回并后台执行

- **WHEN** 用户发起一次评测
- **THEN** 系统立即创建 `eval_run(status=pending)` 并返回 run id，随后后台执行并将状态流转为 running、最终 success 或 failed

#### Scenario: 评测失败记录原因

- **WHEN** 后台执行过程中评测抛出异常
- **THEN** 对应 `eval_run.status` MUST 置为 `failed` 且 `error_msg` 记录失败原因

#### Scenario: 查询运行进度

- **WHEN** 评测处于 running 状态时查询其进度
- **THEN** 系统返回当前阶段与已完成用例数等进度信息

#### Scenario: 进度跨阶段单调不回退

- **WHEN** 评测从一个阶段（如「调用 chatbot」）接近完成切换到下一阶段（如「判分」）时查询进度
- **THEN** 返回的完成百分比 MUST NOT 低于切换前的百分比（按全部阶段总量累计计算），即不出现「近 100% 回到 0%」
