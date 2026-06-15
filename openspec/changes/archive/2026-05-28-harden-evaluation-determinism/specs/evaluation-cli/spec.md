## ADDED Requirements

### Requirement: CLI 必须支持 --repeat N 参数

`medeval run` 子命令 MUST 接受 `--repeat N` 命令行 flag（int 类型，默认 1）。同时 config schema MUST 新增 `run.repeat: int`（默认 1）。CLI 优先级高于 config（CLI 显式提供时覆盖 config 值）。

`--repeat 1` MUST 等价于不传该参数（即沿用旧 config 行为）；`--repeat N>1` MUST 把 N 透传到 `run_cases(repeat=N)` 与 `fold_n_runs`，并使最终报告产物中显示 stability 三态。

#### 场景: CLI 显式覆盖 config

- **WHEN** config.yaml 中 `run.repeat=1`，但 CLI 跑 `medeval run --config config.yaml --repeat 3`
- **THEN** 实际 N MUST 为 3；config 字段不得被静默修改（持久化保留 1）；终端日志必须打印 `running each case 3 times (--repeat=3)`

#### 场景: --repeat 必须为正整数

- **WHEN** 用户跑 `medeval run --repeat 0` 或 `--repeat -1`
- **THEN** CLI MUST 在加载 case 之前给出明确报错（如 `--repeat must be a positive integer (got 0)`）并退出码非 0；不得真去调用 adapter

#### 场景: --repeat 提示在 dry-run 仍生效

- **WHEN** 用户跑 `medeval run --dry-run --repeat 3`
- **THEN** dry-run 输出 MUST 包含 `repeat=3`，便于用户在不真跑时验证配置

### Requirement: 默认 adapter temperature 必须为 0.0

所有内置 adapter（`openai_compat`、`http`）当 `config.adapter.<type>.temperature` 字段缺失或显式为 `null` 时，MUST 使用 `0.0` 作为默认值（而非 `0.3`）。本约束 MUST 在 adapter 构造函数中以默认参数体现，且必须在 README 与 release note 中显著标注此默认值变化。

#### 场景: 未配置 temperature 的旧 config

- **WHEN** config.yaml 中 adapter 段未写 `temperature` 字段
- **THEN** adapter 实例的实际 temperature MUST 为 0.0（不是 0.3）

#### 场景: 显式配置 temperature 不变

- **WHEN** config.yaml 中显式写 `temperature: 0.3`
- **THEN** adapter 实例的 temperature MUST 为 0.3，不被默认值覆盖
