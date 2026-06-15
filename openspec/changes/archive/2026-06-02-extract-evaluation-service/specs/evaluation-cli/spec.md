## ADDED Requirements

### Requirement: 评测编排核心必须以可复用的服务层提供并与 CLI 外壳解耦

评测编排核心 MUST 由独立服务层（`medeval/service.py`）提供，与 CLI 命令式外壳（console 输出、进度条、飞书发布、退出码、flag 解析）解耦：

1. 服务层 MUST 提供功能核 `evaluate(config, cases, adapter, judges, adjudicator, *, progress)`，输入校验后的 `Config` + 用例 + 注入的 adapter/judges/adjudicator，输出 `RunReport`。功能核 MUST NOT 依赖 click、`rich.console` 直接打印、`sys.exit` 或文件写盘；其唯一副作用为 adapter 网络调用。
2. 进度上报 MUST 通过注入式 `ProgressObserver`（默认 `NullProgress` no-op）完成，使功能核不绑定具体 UI（rich）。调用方（CLI）MUST 提供基于 rich 的实现注入。
3. 持久化 MUST 由独立函数（`write_core_artifacts` 写 `report.json` + diff + transcripts，`resolve_diff_target` 解析对比目标）承担，可在临时目录、无网络、无 console 地被测试。
4. 本次重构 MUST 保持 CLI 行为不变：判分结果、报告产物（report.json / report.md / transcripts）、退出码与终端输出与重构前一致。

#### Scenario: 服务层可不经 CLI 直接产出 RunReport

- **当** 调用方注入一个 stub adapter 与最小 judges，调用 `evaluate(...)`
- **那么** MUST 返回一个 `RunReport`，全程不触发 console 打印、不写盘、不调用 `sys.exit`

#### Scenario: 进度上报经注入式 observer

- **当** 以默认 `NullProgress` 调用 `evaluate`
- **那么** MUST 正常完成且无任何进度副作用；当注入记录式 observer 时，MUST 收到各阶段（run/judge_det/...）的 start_phase 与 advance 事件

#### Scenario: CLI 行为保持不变

- **当** 用同一 config 跑 `medeval run`
- **那么** 判分结果、`report.json`/`report.md`/transcripts 产物与退出码 MUST 与重构前一致
