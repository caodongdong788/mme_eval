## MODIFIED Requirements

### Requirement: `run` 子命令必须根据 reporter.formats 配置选择性输出 Markdown 报告

`run` MUST 读取 `reporter.formats`（默认 `["markdown"]`）并只输出列表中包含的格式。`report.json` 与 `transcripts.xlsx` 由基础设施层无条件写盘，不再受 `formats` 控制（参见 `trim-report-formats` / `add-transcript-excel-output`）。

**输出目录 MUST 唯一且不覆盖**：目录名 MUST 为 `<run.name>_<毫秒级 Unix 时间戳>`，落在 `<run.output_dir>/` 下。同一 `run.name` 连续多次评测 MUST NOT 互相覆盖，每次 MUST 产出独立目录；该目录名即版本标识，可被 `--diff-against` 引用，且 MUST 同时作为 `RunReport.run_name`（报告标题与飞书文档名一致）。

**版本对比 MUST 默认自动且可指定/关闭**：对比目标按优先级 `--diff-against`（CLI）> `reporter.diff_against`（config）> 默认。取值语义：留空或 `auto` MUST 自动对比 `outputs/` 下除本次外、按 `report.json` 修改时间最近的一次评测；具体目录名 MUST 对比 `<output_dir>/<名>/report.json`；`none` / `off` MUST 关闭对比。

命中对比目标时 MUST 先写当前 `report.json` 再做 diff，并把 diff 摘要嵌入 Markdown。指定的对比版本不存在时 MUST 提示并跳过 diff，且 MUST NOT 影响本次评测完成；无历史可比时 MUST 跳过 diff。`formats` 含 `"html"` MUST fail-fast 报错。

#### Scenario: formats 含 html 时立即报错

- **WHEN** `reporter.formats: ["html","markdown"]`
- **THEN** CLI MUST 在加载 case 之前以非零退出码退出，错误信息引导用户去掉 "html"

#### Scenario: 同名 run 连跑不覆盖

- **WHEN** `run.name` 保持不变，连续运行 `medeval run` 两次
- **THEN** `outputs/` 下 MUST 出现两个带不同毫秒时间戳后缀的独立目录，旧目录的 `report.json` / `report.md` MUST NOT 被覆盖

#### Scenario: 默认自动对比上一次

- **WHEN** `reporter.diff_against` 留空、且未传 `--diff-against`，`outputs/` 下已存在历史评测
- **THEN** 本次评测 MUST 自动选取按 `report.json` 修改时间最近的历史 run 做 diff，并把摘要嵌入 Markdown

#### Scenario: --diff-against 指定具体版本

- **WHEN** 运行 `medeval run --diff-against doubao_breast_cancer_2026_05_29_v1_1748697930123`
- **THEN** MUST 与该指定目录的 `report.json` 做 diff（优先级高于 config）

#### Scenario: --diff-against none 关闭对比

- **WHEN** 运行 `medeval run --diff-against none`
- **THEN** MUST 跳过 diff，即使 `outputs/` 下存在历史 run

#### Scenario: 指定版本不存在

- **WHEN** `--diff-against` 或 `reporter.diff_against` 指向 `outputs/<名>/report.json` 不存在的目录
- **THEN** 当前评测 MUST 仍然完成，控制台提示"指定的对比版本不存在…跳过 diff"，MUST NOT 报错退出

#### Scenario: 首次评测无历史可比

- **WHEN** `outputs/` 下除本次外没有任何含 `report.json` 的历史 run
- **THEN** MUST 跳过 diff（提示无历史版本可对比），评测照常完成
