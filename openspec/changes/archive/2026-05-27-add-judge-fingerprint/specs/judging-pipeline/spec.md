## 新增需求

### 需求:每个 Judge 必须暴露稳定的 fingerprint 方法

`BaseJudge` 必须提供 `fingerprint(self) -> str` 抽象方法，返回该 Judge 实例的稳定哈希（sha1 前 12 位）。哈希必须覆盖所有"会影响判分结论"的静态属性：HardGateJudge 必须覆盖所有 `_PATTERNS` / `_WORDS` / `_PHRASES` 集合与正则字面量；RuleJudge 必须覆盖 `_normalize` 函数源码与 `self.normalize` 配置；LLMJudge 必须覆盖 `_PROMPT_TEMPLATE`、`self.model`、`self.temperature`、`self.dual_judge`、`self.second_model`。

哈希计算必须使用 `json.dumps(obj, sort_keys=True, ensure_ascii=False)` 序列化以保证跨平台、跨 Python 版本稳定。

#### 场景:同输入多次调用必须返回相同 fingerprint

- **当** 同一进程内对同一个 `HardGateJudge` 实例两次调用 `fingerprint()`
- **那么** 必须返回完全相同的 12 位字符串

#### 场景:修改 pattern 内容必须改变 fingerprint

- **当** 在 `hard_gate.py` 的 `_EMERGENCY_PATTERNS` 中新增一条正则后重新加载
- **那么** 新实例的 `fingerprint()` 必须与旧版本不同

#### 场景:修改注释不应改变 fingerprint

- **当** 在 `_EMERGENCY_PATTERNS` 上方加一行 `# 新增的注释`，但 patterns 列表内容不变
- **那么** `fingerprint()` 返回值必须不变

#### 场景:LLMJudge 改 temperature 必须改变 fingerprint

- **当** 构造两个 `LLMJudge`，一个 `temperature=0.0`、一个 `temperature=0.3`，其他参数相同
- **那么** 两者的 `fingerprint()` 必须不同

### 需求:JudgeVerdict 必须携带 judge_fingerprint 字段

`JudgeVerdict` 必须新增 `judge_fingerprint: str` 字段，默认空字符串（向后兼容历史报告）。`aggregator.judge_all` 必须在收集各 Judge 的 verdicts 时统一把对应 Judge 的 fingerprint 写入这些 verdict 的字段。

#### 场景:每条 verdict 都带 fingerprint

- **当** 评测一条用例由 `HardGateJudge + RuleJudge` 同时判分
- **那么** 返回的 verdicts 中，所有 `hard_gate.*` 必须共享一个 fingerprint（=HardGateJudge.fingerprint()），所有 `rule.*` 必须共享另一个 fingerprint

#### 场景:历史 JSON 反序列化不破坏

- **当** 加载 P0 时代的 outputs/doubao_baseline/report.json（无 `judge_fingerprint` 字段）
- **那么** `RunReport.model_validate_json(...)` 必须成功，所有 verdict 的 `judge_fingerprint` 必须为空字符串
