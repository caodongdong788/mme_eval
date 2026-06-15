## Why

此前 `medeval run` 的输出目录直接等于 `run.name`（如 `outputs/doubao_breast_cancer_2026_05_29_v1/`）。两个问题：

1. **会覆盖**：不改 `run.name` 连跑两次，同名目录被原地覆盖，`report.json` / `report.md` 旧结果丢失，无法留痕。
2. **对比要手填**：版本间 diff 依赖手动在 `reporter.diff_against` 填上一次 run 名，忘填就没有 diff。

我们希望「每次评测都是独立文件夹、默认自动和上一次比、也能指定具体版本比」。

## What Changes

- **每次评测落到唯一目录**：目录名 = `run.name` + `_` + 毫秒级 Unix 时间戳（`run.name` 已含年月日+版本号，故不重复日期）。同名 `run.name` 连跑多次不再互相覆盖；目录名即版本标识。
- **默认自动对比上一次**：`reporter.diff_against` 留空或 `auto` 时，自动选 `outputs/` 下除本次外、按 `report.json` 修改时间最近的一次评测做 diff。
- **可指定/关闭对比**：新增 CLI `--diff-against`，优先级 `--diff-against` > `reporter.diff_against` > 默认自动。取值 `none`/`off` 关闭对比；具体目录名对比指定版本；指定版本不存在时提示并跳过、不影响本次评测。
- 不改任何判分逻辑（hard_gate / rule / llm / scoring_point 指纹不变）。

## Capabilities

### New Capabilities
<!-- 无新增 capability -->

### Modified Capabilities
- `evaluation-cli`: `run` 子命令 MUST 把结果写入唯一时间戳目录（不覆盖）；版本对比 MUST 默认自动对比上一次，并 MUST 支持 `--diff-against` 指定/关闭。

## Impact

- 代码：`medeval/cli.py`（`run_slug` 生成、`_find_previous_run` 辅助、`--diff-against` flag、diff 目标解析）。
- 配置：`config.yaml` 的 `reporter.diff_against` 注释更新（留空=自动 / 目录名=指定 / none=关闭）。
- 文档：`AGENTS.md` §4 常用命令 / §3 目录地图 / §8 易踩的坑；`README.md` 启动方式与输出目录说明。
- 兼容性：旧的「填具体 run 名做 diff」仍可用（视为指定版本）；判分行为与历史 `report.json` 结构不变。
- 副作用：`outputs/` 不再覆盖、会持续累积，需自行清理旧 run（本期不引入自动清理）。
