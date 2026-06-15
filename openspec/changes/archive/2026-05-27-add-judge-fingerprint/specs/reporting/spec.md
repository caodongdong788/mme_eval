## 新增需求

### 需求:RunReport 必须聚合 judge_fingerprints 顶层字段

`RunReport` 必须新增 `judge_fingerprints: dict[str, str]` 字段（key=Judge name，value=12 位 fingerprint），默认空字典（向后兼容）。`build_report` 必须在聚合时，从首个 CaseResult 的 verdicts 中收集 `judge_name → fingerprint` 写入该字段；若不同用例上的同一 judge 出现不同 fingerprint 值（理论上不应发生），必须抛 `ValueError` 提示判分不一致。

#### 场景:报告顶层正确聚合 fingerprint

- **当** 评测包含 30 条用例，使用 HardGate + Rule 两个 Judge
- **那么** `RunReport.judge_fingerprints` 必须形如 `{"hard_gate": "a3f1c2d4e5f6", "rule": "789abcdef012"}`

#### 场景:同 run 内 fingerprint 必须一致

- **当** 由于程序错误，第 5 条用例的 hard_gate verdicts 携带的 fingerprint 与第 1 条不同
- **那么** `build_report` 必须抛 `ValueError`，错误消息必须指出冲突的 fingerprint 与首个不同 verdict 的位置

## 修改需求

### 需求:系统必须支持与上次评测的 regression / improvement diff

`diff_runs(current_path, previous_path)` 必须基于两份 JSON 报告输出 Markdown 片段，包含：总通过率与 delta（百分点），分 level 通过率对比表，regression 列表（上次过、本次挂的 sample_id），improvement 列表（上次挂、本次过的 sample_id）。若 `previous_path` 不存在，必须返回提示信息而不抛错。

**新增约束**：`diff_runs` 必须先比较两份 report 顶层的 `judge_fingerprints`。若任一 judge 在两侧的 fingerprint 不一致（或缺失），必须在输出 Markdown 顶部插入显眼的 ⚠️ 警告块，列出每个 judge 的当前 / 上版本 fingerprint，并提示 regression / improvement 列表可能包含"判分逻辑变化"导致的伪差异。regression / improvement 列表仍照常输出。

#### 场景:上版本报告缺失

- **当** `previous_path` 文件不存在
- **那么** `diff_runs` 必须返回类似"_未找到上版本报告 ..._"的友好提示，不得抛出 IOError

#### 场景:列出 regression sample_id

- **当** 上版本 `sample_id=l3_acute_mi` 是 passed，本版本变成 fail
- **那么** diff Markdown 中 regression 列表必须含 `l3_acute_mi`，并以反引号包裹

#### 场景:regression 列表数量必须有上限

- **当** 一次评测产生 50 条 regression
- **那么** diff Markdown 最多列出 20 条（避免飞书文档过长），后续可由 JSON 详查

#### 场景:Judge fingerprint 不一致时必须警告

- **当** 当前 report 的 `hard_gate` fingerprint 是 `a3f1c2` 但上版本是 `b7e2d8`
- **那么** diff Markdown 必须在顶部插入"⚠️ Judge 版本不一致"块，含 judge 名、当前/上版本 fingerprint，并提示 regression 列表中可能包含伪差异

#### 场景:历史报告无 fingerprint 字段

- **当** 上版本是 P0 时代的 report.json（顶层无 `judge_fingerprints`）
- **那么** diff Markdown 必须在警告块中把上版本各 judge 的 fingerprint 标记为"未知 (历史报告)"，并照常输出 regression / improvement
