## MODIFIED Requirements

### 需求:CLI 必须提供 run / validate / list-cases 三个子命令

CLI MUST 用 click group 提供以下子命令：

- `medeval run`：跑一次完整评测并输出报告
- `medeval validate`：仅加载所有用例做 schema 校验，不调用 Adapter
- `medeval list-cases`：以 Rich 表格列出全部用例（sample_id / level / scenario / sub_scenario / score_profile）

所有子命令 MUST 默认读 `./config.yaml`，并支持 `--config` 指向其他配置。

#### Scenario: 无网络下做用例自检

- **WHEN** 在 CI 上运行 `medeval validate --config config.yaml`
- **THEN** MUST 不调用任何 Adapter，仅返回"N 条用例校验通过"或在校验失败时以非零退出码退出

#### Scenario: list-cases 不读取 secrets

- **WHEN** 运行 `medeval list-cases` 而环境变量没有任何 API key
- **THEN** 命令 MUST 正常输出表格，不得因缺 key 失败
