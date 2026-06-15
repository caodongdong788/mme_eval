## 新增需求

### 需求:CLI 必须提供 verify-heuristics 子命令做本地三检

CLI 必须新增 `medeval verify-heuristics` 子命令，把以下三项检查作为单一入口串联运行：

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
