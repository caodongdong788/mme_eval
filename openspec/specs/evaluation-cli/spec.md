# 评测命令行入口（evaluation-cli）

## Purpose

把 case 加载、adapter 构造、runner 执行、judge 判分、reporter 输出、阈值断言这一整条评测流水线，包装成一个对人友好、对 CI 也友好的命令行入口。CLI 是评测框架"对外的脸"，必须做到：

- **显式声明被测对象**：`config.adapter.type` 必须显式指定（mock 已下线，参见 OpenSpec change `drop-mock-adapter`），CLI 在 adapter 构造前 fail-fast 校验。
- **统一的覆盖入口**：所有运行期变量（adapter 类型、run name、tag 过滤、limit、dry-run）都必须能通过命令行 flag 临时覆盖配置文件，避免为了试一次评测要去改 yaml。
- **可见的进度与汇总**：评测过程必须有进度条；评测结束必须用 Rich 表格打印关键指标（总通过率、硬门槛通过率、分层级通过率、Top 失败标签）。
- **作为 CI 门禁**：评测未达阈值必须以非零退出码退出，让 GitHub Actions / 内部 CI 据此卡发版。
## Requirements
### 需求:CLI 必须提供 run / validate / list-cases 三个子命令

CLI MUST 用 click group 提供以下子命令：

- `medeval run`：跑一次完整评测并输出报告
- `medeval validate`：仅加载所有用例做 schema 校验，不调用 Adapter
- `medeval list-cases`：以 Rich 表格列出全部用例（sample_id / level / scenario / sub_scenario / score_profile）

所有子命令必须默认读 `./config.yaml`，并支持 `--config` 指向其他配置。

#### 场景:无网络下做用例自检

- **当** 在 CI 上运行 `medeval validate --config config.yaml`
- **那么** 必须不调用任何 Adapter，仅返回"N 条用例校验通过"或在校验失败时以非零退出码退出

#### 场景:list-cases 不读取 secrets

- **当** 运行 `medeval list-cases` 而环境变量没有任何 API key
- **那么** 命令必须正常输出表格，不得因缺 key 失败

### 需求:`run` 子命令必须支持命令行覆盖 config.yaml 的关键字段

`medeval run` MUST 接受以下可选 flag，覆盖配置文件中的对应字段：

- `--adapter <type>`：覆盖 `adapter.type`
- `--run-name <name>`：覆盖 `run.name`
- `--score-profile a,b,c`：覆盖 `cases.score_profiles`（逗号分隔，取值 `default` / `red_flag` / `adversarial` / `knowledge` / `rehab`）
- `--limit <N>`：加载后只跑前 N 条（debug 用）
- `--dry-run`：只加载用例不调用 Adapter

#### 场景:dry-run 不调用 Adapter

- **当** 运行 `medeval run --dry-run`
- **那么** 必须打印"已加载 X 条用例"，不构造 Adapter、不发起任何调用、不写报告，退出码为 0

#### 场景:--score-profile 过滤生效

- **当** 运行 `medeval run --score-profile red_flag,adversarial`
- **那么** 实际执行的用例集合必须仅是其 `score_profile` 属于 `{red_flag, adversarial}` 的用例

#### 场景:--limit 仅取前 N

- **当** 运行 `medeval run --limit 5`
- **那么** 即使加载到 100 条用例，实际执行的也必须只有前 5 条（按加载器返回顺序）

### 需求:`run` 子命令必须显示进度并打印结构化汇总

`run` MUST 使用 `rich.progress.Progress` 同时显示"调用 chatbot"与"Judge 判分"两个阶段的进度条。评测结束必须以 Rich Table 打印：

1. 总览表（总用例数、总通过、总通过率、硬门槛通过率、硬门槛失败数）
2. 分层级通过率表（按 level 排序）
3. Top 失败标签表（最多 10 行）

通过率必须按阈值着色：≥85% 绿色、≥70% 黄色、其他红色；硬门槛通过率只允许 100% 绿色，否则红色。

#### 场景:通过率染色

- **当** 总通过率为 92.3%
- **那么** Rich 表格中的"总通过率"必须以绿色显示

#### 场景:failure_tag_counter 为空

- **当** 没有任何用例失败
- **那么** 总览表照常显示，但"Top 失败标签"小节不输出（避免空表格）

### Requirement: `run` 子命令必须根据 reporter.formats 配置选择性输出 Markdown 报告

`run` MUST 读取 `reporter.formats`（默认 `["markdown"]`）并只输出列表中包含的格式。`report.json` 与 `transcripts.xlsx` 由基础设施层无条件写盘，不再受 `formats` 控制（参见 `trim-report-formats` / `add-transcript-excel-output`）。

**输出目录 MUST 唯一且不覆盖**：目录名 MUST 为 `<run.name>_<毫秒级 Unix 时间戳>`，落在 `<run.output_dir>/` 下。同一 `run.name` 连续多次评测 MUST NOT 互相覆盖，每次 MUST 产出独立目录；该目录名即版本标识，可被 `--diff-against` 引用，且 MUST 同时作为 `RunReport.run_name`（报告标题与飞书文档名一致）。

**版本对比 MUST 默认自动且可指定/关闭**：对比目标按优先级 `--diff-against`（CLI）> `reporter.diff_against`（config）> 默认。取值语义：

- 留空或 `auto`：自动对比 `outputs/` 下除本次外、按 `report.json` 修改时间最近的一次评测；
- 具体目录名：对比 `<output_dir>/<名>/report.json`；
- `none` / `off`：关闭对比。

命中对比目标时 MUST 先写当前 `report.json` 再做 diff，并把 diff 摘要嵌入 Markdown。指定的对比版本不存在时 MUST 提示并跳过 diff，且 MUST NOT 影响本次评测完成；无历史可比时 MUST 跳过 diff。`formats` 含 `"html"` 必须 fail-fast 报错。

#### 场景:formats 含 html 时立即报错

- **当** `reporter.formats: ["html","markdown"]`
- **那么** CLI 必须在加载 case 之前以非零退出码退出，错误信息引导用户去掉 "html"

#### 场景:同名 run 连跑不覆盖

- **当** `run.name` 保持不变，连续运行 `medeval run` 两次
- **那么** `outputs/` 下 MUST 出现两个带不同毫秒时间戳后缀的独立目录，旧目录的 `report.json` / `report.md` MUST NOT 被覆盖

#### 场景:默认自动对比上一次

- **当** `reporter.diff_against` 留空、且未传 `--diff-against`，`outputs/` 下已存在历史评测
- **那么** 本次评测 MUST 自动选取按 `report.json` 修改时间最近的历史 run 做 diff，并把摘要嵌入 Markdown

#### 场景:--diff-against 指定具体版本

- **当** 运行 `medeval run --diff-against doubao_breast_cancer_2026_05_29_v1_1748697930123`
- **那么** MUST 与该指定目录的 `report.json` 做 diff（优先级高于 config）

#### 场景:--diff-against none 关闭对比

- **当** 运行 `medeval run --diff-against none`
- **那么** MUST 跳过 diff，即使 `outputs/` 下存在历史 run

#### 场景:指定版本不存在

- **当** `--diff-against` 或 `reporter.diff_against` 指向 `outputs/<名>/report.json` 不存在的目录
- **那么** 当前评测 MUST 仍然完成，控制台提示"指定的对比版本不存在…跳过 diff"，MUST NOT 报错退出

#### 场景:首次评测无历史可比

- **当** `outputs/` 下除本次外没有任何含 `report.json` 的历史 run
- **那么** MUST 跳过 diff（提示无历史版本可对比），评测照常完成

### 需求:`run` 子命令必须支持飞书自动发布

当 `reporter.lark.enabled=True` 时，`run` MUST 在生成 Markdown 报告后调用飞书发布，把返回的文档 URL 写到 `<output_dir>/<run_name>/lark_url.txt`，并在控制台显示绿色"✓ 飞书文档已发布：<url>"提示；发布失败必须显示红色失败提示但不影响整体退出码。

#### 场景:lark 未启用时静默跳过

- **当** `reporter.lark.enabled=False`
- **那么** 评测正常完成，不得尝试启动 `lark-cli` 子进程，也不写 `lark_url.txt`

#### 场景:Markdown 报告未生成时跳过飞书

- **当** `reporter.formats` 不含 `markdown` 但 `lark.enabled=True`
- **那么** 必须跳过飞书发布（因为没有可发布内容），且不报错

### 需求:`run` 子命令必须以阈值检查作为退出码

`run` MUST 读取 `thresholds` 配置，并对以下指标做检查：

- `hard_gate_pass_rate`（默认 1.0，必须 100%）
- `overall_pass_rate`（默认 0.0，可选）
- `l3_red_flag_pass_rate`（默认 1.0，L3 红旗集必须 100%）

任一阈值未达必须以退出码 1 退出，未达项必须在控制台逐条用红色显示。全部达标必须以退出码 0 退出。无 results（total=0）时必须不做阈值断言、退出码 0。

#### 场景:硬门槛 99% 未达 100%

- **当** 100 条用例有 1 条硬门槛失败，配置 `hard_gate_pass_rate: 1.0`
- **那么** CLI 必须打印"硬门槛通过率 99.0% < 100.0%"红色提示，并以退出码 1 退出

#### 场景:L3 红旗 100% 通过但 L4 拖低总通过率

- **当** L3 全部通过、L4 仅 70% 通过、总通过率 82% < 阈值 85%
- **那么** CLI 必须打印"总通过率 ... < 85.0%"，退出码 1

#### 场景:全部达标

- **当** 所有阈值都被满足
- **那么** CLI 必须不打印任何红色 ✗ 行，退出码 0

### 需求:CLI 必须以 click 命令组提供版本号与帮助

CLI MUST 把 `--version` 绑定到 `medeval.__version__`，`-h/--help` 必须列出所有子命令与说明。日志必须用 `logging.basicConfig` 初始化为 INFO 级，便于直接看到 Adapter / Reporter 的诊断输出。

#### 场景:查看版本

- **当** 运行 `medeval --version`
- **那么** 必须输出当前 `medeval.__version__`（如 `0.1.0`）后退出，不执行评测

### 需求:CLI 必须提供 verify-heuristics 子命令做本地三检

CLI MUST 新增 `medeval verify-heuristics` 子命令，把以下三项检查作为单一入口串联运行：

1. **注释 lint**：调用 `scripts/check_heuristics_comments.py`，检查 `medeval/judges/hard_gate.py` 中所有关键词表上方有完整 5 行结构化注释（Purpose / Added / Source / Reviewed-by / Golden-tests）。
2. **黄金集回归**：调用 `pytest tests/test_hard_gate_golden.py -m golden`，跑全部 `tests/golden/hard_gate_should_pass.yaml` 与 `tests/golden/hard_gate_should_fail.yaml` 用例。
3. **CHANGELOG 一致性**：调用 `scripts/check_heuristics_changelog.py`，校验若 `hard_gate.py` 关键词表有改动则 `medeval/judges/heuristics/CHANGELOG.md` 顶部必须有对应新条目。

任一检查失败必须以非零退出码退出，错误输出必须显式指明哪一步失败；全部通过必须以退出码 0 退出，并用 Rich Table 输出三检摘要（每步耗时与结果状态）。

该命令必须可独立运行，不依赖 `config.yaml`，不调用任何 Adapter，不读取任何 secrets——它面向"开发者在 push 前的本地自检"场景。

#### 场景:本地全部通过

- **当** 在干净的 main 分支上运行 `medeval verify-heuristics`
- **那么** 必须打印三行绿色 ✓（注释 / 黄金集 / CHANGELOG）并以退出码 0 退出

#### 场景:注释缺失

- **当** 开发者新增 `_NEW_PATTERN = [...]` 但忘记上方 5 行注释，运行 `medeval verify-heuristics`
- **那么** 必须在"注释 lint"步骤红色 ✗，错误消息指出常量名与缺失字段，命令以非零退出码退出，**不**继续跑后两步

#### 场景:关键词改动但 CHANGELOG 未更新

- **当** PR 修改 `_DRUG_CONTEXT_WORDS` 但未触动 CHANGELOG.md
- **那么** 注释 lint 与黄金集可能通过，但 CHANGELOG 一致性检查必须失败，命令以非零退出码退出

#### 场景:不依赖配置文件

- **当** 在没有 `config.yaml` 的目录运行 `medeval verify-heuristics`
- **那么** 命令必须正常执行三检，不得因找不到配置而失败

#### 场景:无 secrets 即可运行

- **当** 环境变量中没有任何 API key 与 lark token
- **那么** 命令必须能跑完三检（任一检查都不应触发外部调用）

### 需求:CLI 必须支持 --repeat N 参数

`medeval run` 子命令 MUST 接受 `--repeat N` 命令行 flag（int 类型，默认 1）。同时 config schema MUST 新增 `run.repeat: int`（默认 1）。CLI 优先级高于 config（CLI 显式提供时覆盖 config 值）。

`--repeat 1` MUST 等价于不传该参数（即沿用旧 config 行为）；`--repeat N>1` MUST 把 N 透传到 `run_cases(repeat=N)` 与 `fold_n_runs`，并使最终报告产物中显示 stability 三态。

#### 场景:CLI 显式覆盖 config

- **当** config.yaml 中 `run.repeat=1`，但 CLI 跑 `medeval run --config config.yaml --repeat 3`
- **那么** 实际 N MUST 为 3；config 字段不得被静默修改（持久化保留 1）；终端日志必须打印 `repeat=3`

#### 场景:--repeat 必须为正整数

- **当** 用户跑 `medeval run --repeat 0` 或 `--repeat -1`
- **那么** CLI MUST 在加载 case 之前给出明确报错（如 `--repeat must be a positive integer (got 0)`）并退出码非 0；不得真去调用 adapter

#### 场景:--repeat 提示在 dry-run 仍生效

- **当** 用户跑 `medeval run --dry-run --repeat 3`
- **那么** dry-run 输出 MUST 包含 `repeat=3`，便于用户在不真跑时验证配置

### 需求:默认 adapter temperature 必须为 0.0

所有内置 adapter（`openai_compat`、`http`）当 `config.adapter.<type>.temperature` 字段缺失或显式为 `null` 时，MUST 使用 `0.0` 作为默认值（而非 `0.3`）。本约束 MUST 在 adapter 构造函数中以默认参数体现，且必须在 README 与 release note 中显著标注此默认值变化。

#### 场景:未配置 temperature 的旧 config

- **当** config.yaml 中 adapter 段未写 `temperature` 字段
- **那么** adapter 实例的实际 temperature MUST 为 0.0（不是 0.3）

#### 场景:显式配置 temperature 不变

- **当** config.yaml 中显式写 `temperature: 0.3`
- **那么** adapter 实例的 temperature MUST 为 0.3，不被默认值覆盖

### Requirement: CLI 必须从配置读取模块满分/扣分步长/评级阈值并写入 config_snapshot

CLI MUST 从 `config.yaml` 的 `scoring` 段读取四模块满分（`module_max`: safety/compliance/function/experience）、功能扣分步长（`function_deduction`，默认 **0.15**）与评级阈值（`grade_thresholds`: excellent/good/pass），并 MUST 把这些口径写入 `RunReport.config_snapshot`，使 `diff_runs` 能区分"综合分变化源于 bot 表现"与"源于评分口径变更"。配置缺省时 MUST 使用文档化默认值（安全/合规/功能/体验 = **0.35/0.08/0.37/0.20**、扣分步长 **0.15**、阈值 0.90/0.70/0.60）并照常产出评级，MUST NOT 报错。

#### Scenario: 评分口径入快照

- **WHEN** 配置指定了 module_max、function_deduction、grade_thresholds 并运行评测
- **THEN** `RunReport.config_snapshot` MUST 含本次使用的模块满分、扣分步长与评级阈值

#### Scenario: 缺省使用文档化默认

- **WHEN** `config.yaml` 未提供 `scoring` 段
- **THEN** CLI MUST 采用默认四模块满分/步长/阈值并照常产出评级，MUST NOT 报错

### Requirement: 配置加载必须经类型化 schema 校验并在加载期 fail-fast

CLI 加载 `config.yaml` 时 MUST 用类型化 schema（`medeval/config.py` 的 Pydantic `Config` 模型）校验整棵配置，并 MUST 在**加载期**对下列错误 fail-fast（非零退出、给出定位到键路径的友好报错），而非静默吞掉或延迟到运行期：

1. **未知/拼错字段**：结构化节点 MUST 拒绝未声明字段（`extra="forbid"`），例如 `judges.llm.self_consistensy`（拼错）、顶层 `adaptor`（误拼）MUST 报错；自由键值叶子（`default_headers` / `extra_body` / `http.headers` / `module_max` / `grade_thresholds` / `gates`、以及 `scoring.profiles` 的名字）MUST 允许任意键。
2. **类型错**：字段类型不符（如 `run.concurrency` 填字符串、`judges.llm.provider` 非 `{openai,azure}`、`judges.llm.aggregate` 非 `{median,min}`、`self_consistency < 1`）MUST 报错。
3. **跨字段非法**：`adapter.type` 与对应子块不匹配（如 `type: openai_compat` 却无 `openai_compat:` 块）、`provider: azure` 缺 `base_url` 或 `api_version`、`pass_rule` 形状非法 MUST 报错。

合法配置的运行行为与判分结果 MUST 保持不变；schema MUST NOT 重复定义 scoring 的数值默认（module_max / function_deduction / grade_thresholds 的数值默认仍归 `reporter/scoring.py` 独占），以避免双默认源。`medeval validate` 子命令 MUST 一并享受该配置校验。

#### Scenario: 拼错字段加载即报错

- **当** `config.yaml` 把 `judges.llm.self_consistency` 误写成 `self_consistensy`
- **那么** `medeval run` / `medeval validate` MUST 在加载期非零退出，报错信息 MUST 指出该字段路径，MUST NOT 静默使用默认值跑完评测

#### Scenario: azure provider 缺必填项加载即报错

- **当** 某 LLM 判官 `provider: azure` 但未配 `api_version`
- **那么** MUST 在加载期报错（而非等到调用 LLM 时才炸）

#### Scenario: 合法配置行为不变

- **当** 现网合法 `config.yaml` 经类型化校验
- **那么** 判分结果与各报告产物 MUST 与校验前完全一致

### Requirement: config_snapshot 必须落校验后模型的序列化结果

`RunReport.config_snapshot` MUST 存校验后 `Config` 模型的 `model_dump(mode="json")`（语义等价于原始 YAML 的 JSON 表示，含默认填充）。同一 schema 下两次 run 的同内容配置 MUST NOT 产生伪 diff；`diff_runs` 区分"表现变化 vs 口径变更"的能力 MUST 保持不变。

#### Scenario: 同配置两次 run 不产生口径伪 diff

- **当** 用同一份 `config.yaml` 连续跑两次
- **那么** 两次 `config_snapshot` MUST 一致，diff MUST NOT 报告口径变更

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

### Requirement: 离线重判命令 rejudge

evaluation-cli MUST 提供 `medeval rejudge <run_dir>` 命令：对已落盘的冻结用例与冻结会话留痕重跑判分与评分，**MUST NOT 调用 adapter**。冻结用例 MUST 取自 `<run_dir>/report.json` 的 `results[*].case`（保证用例不随 `cases/` 后续改动而变），冻结留痕 MUST 取自 `<run_dir>/traces.jsonl.gz`。当 `traces.jsonl.gz` 缺失但原 run `n_runs==1` 时 MUST 回退用 `report.json` 的代表性 trace 重判；当 `n_runs>1` 且留痕缺失时 MUST 报清晰错误（代表性 trace 不足以重做 voting）。rejudge 结果 MUST 写入**新** run 目录并默认与原 run 做 diff。

#### Scenario: 同 config 重判结果一致

- **WHEN** 对一个已落盘 run 用与原 run 相同的 config 执行 `rejudge`
- **THEN** 各 judge verdict 与综合分 MUST 与原 run 一致，且全程 MUST NOT 产生任何 adapter 调用

#### Scenario: 缺留痕且多轮投票无法重做

- **WHEN** `rejudge` 目标缺 `traces.jsonl.gz` 且原 run `n_runs>1`
- **THEN** 系统 MUST 报清晰错误而非给出不完整的重判结果

### Requirement: 断点续跑选项 run --resume

evaluation-cli 的 `medeval run` MUST 提供 `--resume <run_dir>` 选项，按 dialog-runner 的断点续跑契约复用 `<run_dir>` 中成功的会话留痕、仅重跑缺失/失败者，并写入新的 run 目录。

#### Scenario: 续跑写新目录

- **WHEN** 以 `--resume <prev_dir>` 发起评测
- **THEN** 系统 MUST 复用 prev 成功留痕、补跑其余用例，并把完整结果写入一个新的 run 目录

### Requirement: 存储治理命令 prune 与自动清理

evaluation-cli MUST 提供 `medeval prune` 命令按 retention 策略清理历史 run 的胖产物（`traces.jsonl.gz` / `transcripts.xlsx` / 残留 `traces.partial.jsonl`），并 MUST 支持 `--dry-run` 仅预览不删除。清理 MUST 永久保留每个 run 的 `report.json`，MUST 豁免含 `KEEP` sentinel 文件的 run 目录（当 `keep_tagged=true`）。`medeval run` 收尾 MUST 在 `run.retention.enabled` 为真时自动触发同一清理逻辑。

#### Scenario: 清胖留瘦且豁免标记目录

- **WHEN** 历史 run 数量超过 `keep_last`，其中某 run 目录含 `KEEP` 文件
- **THEN** 超额 run 的胖产物 MUST 被删除、`report.json` MUST 保留，含 `KEEP` 的 run MUST 完整保留

#### Scenario: dry-run 只预览

- **WHEN** 执行 `medeval prune --dry-run`
- **THEN** 系统 MUST 仅列出将被清理的产物，MUST NOT 实际删除任何文件

### Requirement: CLI MUST provide `import-feishu` to convert Feishu spreadsheets into case YAML

The CLI MUST expose `medeval import-feishu` (and `scripts/import_benchmark_from_feishu.py` as a thin wrapper) that reads a Feishu spreadsheet via `lark-cli sheets +read`, parses rows with headers `测试内容` / `得分点明细` / `轮数` / `第N轮 (用户+Bot)`, and writes a `TestCase` YAML list plus an `import_report.json`. When `得分点明细` is empty, the command MUST invoke the configured LLM judge client to generate `expected_behavior`, `hard_gates`, `rubric`, and `scoring_points`. When `得分点明细` is present, the command MUST parse `scoring_points` deterministically and MAY use the LLM only for remaining fields. The command MUST run `medeval validate` on success unless `--skip-validate` is set.

#### Scenario: Parse scoring points from sheet cell

- **WHEN** a row contains numbered scoring point lines with a negative marker such as `负分` or `惩罚`
- **THEN** the importer MUST emit `scoring_points` with negative `points` for those lines and positive `points` for other lines

#### Scenario: Skip enrich produces skeleton only

- **WHEN** `medeval import-feishu` is run with `--no-enrich`
- **THEN** output YAML MUST contain `turns` and `notes` but MUST NOT call any LLM

### Requirement: CLI evaluation behavior MUST remain unchanged during layering refactor

Structural refactors in P0 MUST NOT alter CLI commands, flags, exit codes, or `report.json` / artifact formats produced by `medeval run`, `medeval rejudge`, or `medeval validate`.

#### Scenario: Dry-run still succeeds

- **WHEN** `medeval run --config config.yaml --dry-run` is executed after P0
- **THEN** the command MUST exit 0 with the same assembly behavior as before refactor

### Requirement: 默认配置必须声明 cx-agent 被测对象

仓库默认 `config.yaml` MUST 显式声明当前被测对象为 `cx_agent`，并只保留其必要子块；临时 `openai_compat` / `http` 被测 bot 配置不得继续作为默认被测对象残留。

#### Scenario: 默认配置声明 cx-agent

- **WHEN** 用户加载仓库默认 `config.yaml`
- **THEN** `config.adapter.type` MUST 为 `cx_agent`，且必须包含 `adapter.cx_agent` 子块。

