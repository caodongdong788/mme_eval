## Why

`cli.run()` 是一个 ~390 行的 god-function，顺序扛了 18 件事：config 加载/覆盖、repeat 解析、formats 校验、用例加载、dry-run、adapter/judges/adjudicator 构造、四阶段并发判分流水（`_go`）、`build_report`、总览打印、写 `report.json`/`report.md`、formats 过滤、diff 目标解析+`diff_runs`、transcripts.xlsx 生命周期、飞书 sheet/doc 发布、阈值断言+`sys.exit`。

后果：

- **核心编排不可复用**：SDK / CI / 批量场景想"跑评测拿 `RunReport`"必须穿过 click + console + sys.exit。
- **难测**：最有价值的编排（run→judge→fold→report）与 rich 进度条、文件写盘、飞书 SDK、退出码缠在一起，无法不触网/不写盘地单测。
- **关注点混杂**：网络副作用、文件副作用、飞书副作用、终端 UI、进程退出码全挤在一个函数里。

研发阶段，行为零变化前提下做结构重构。

## What Changes

按"功能核 / 命令式外壳"分层，新增 `medeval/service.py`（无 console / 无 click / 无 sys.exit）：

- **进度解耦**：`ProgressObserver` Protocol（`start_phase` / `advance`）+ `NullProgress`（默认 no-op）。功能核只发 phase 事件，不绑 rich。
- **构造器迁入并公开**：`build_judges(judges_cfg)` / `build_adjudicator(judges_cfg)`（原 `cli._build_judges`/`_build_adjudicator`）。
- **功能核**：`evaluate(config, cases, adapter, judges, adjudicator, *, progress=NullProgress()) -> RunReport`——即原 `_go` 全流程 + `build_report`；唯一副作用是 adapter 网络调用；`adapter/judges/adjudicator` 由调用方注入（SDK/测试可塞 stub）。
- **持久化层**：`resolve_diff_target(...) -> Path | None`（纯解析 none/off/auto/具体名）+ `write_core_artifacts(report, out_dir, *, prev_json) -> Artifacts`（写 json + diff + transcripts.xlsx，无 console / 无网络）；`_find_previous_run` 迁入。
- **CLI 变薄**：`cli.run` 只做 flag 解析、config 加载/覆盖、dry-run、`build_adapter`（留 CLI）、打印 fingerprint、注入 `RichProgress` 调 `evaluate`、打印总览、`write_core_artifacts`、飞书 sheet/doc 发布、`write_markdown`、阈值断言+`sys.exit`。

## Capabilities

### Modified Capabilities
- `evaluation-cli`：新增"评测编排核心 MUST 以可复用的服务层（`medeval/service.py`）提供，与 CLI 外壳（console / 飞书 / 退出码 / 进度条）解耦；功能核 `evaluate(...)` 不得依赖 click / console / sys.exit，进度通过注入式 `ProgressObserver` 上报"的要求。CLI 行为（判分、报告产物、退出码）保持不变。

## Impact

- 代码：新增 `medeval/service.py`；`medeval/cli.py` 变薄（`run` 拆解、`_build_judges`/`_build_adjudicator`/`_find_previous_run` 迁入 service 并改为公开 API）；新增 `tests/test_service.py`。
- 行为：判分结果、报告产物、退出码、终端输出**全部不变**（纯结构重构）；现有 e2e（`test_report_formats_default`）继续绿（adapter 仍在 CLI 构造，monkeypatch 目标不变）。
- 兼容性：内部重构，无对外 schema / report 字段变化。
- 依赖：不引入新依赖。
