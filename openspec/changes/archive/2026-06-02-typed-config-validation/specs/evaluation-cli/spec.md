## ADDED Requirements

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
