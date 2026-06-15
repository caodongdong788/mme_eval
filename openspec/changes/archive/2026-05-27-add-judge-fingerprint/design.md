## 上下文

```
                    ┌──────────────────────────┐
   case.yaml ───┐   │  Judge                   │
                ├──▶│  ┌──────────────────────┐│       JudgeVerdict
   bot reply ───┤   │  │ _PATTERNS / _WORDS   ││──▶ ┌────────────────┐
                │   │  │ _PROMPT_TEMPLATE     ││    │ passed         │
   config ──────┘   │  │  (隐式内嵌!)         ││    │ reason         │
                    │  └──────────────────────┘│    │ evidence       │
                    └──────────────────────────┘    │ failure_tags   │
                                                    └────────────────┘
                                                            │
                                                            ▼
                                                       report.json
                                                       config_snapshot
                                                       （只记录 yaml 配置）
```

`config_snapshot` 已经把 `judges.llm.model="gpt-4o-mini"` 这类 yaml 配置序列化了，但是**真正影响判分的规则代码**完全是隐式的。改任意一个 `_PATTERN` 都不会留下机器可读的痕迹。

P1 即将做的事：(1) LLM-as-Judge 默认开启；(2) 与上版本 diff 作为 reporter 默认能力。这两件事都对"判分函数是否稳定"高度敏感。

## 目标 / 非目标

**目标：**

- 让 `diff_runs` 能够在两份 report 的 judge 不同（哪怕只是 prompt 改了一个标点）时立刻识别并显式提示，避免把"判分变化"误归因为"bot 退化"。
- 任何对 Judge 内嵌规则的修改必须在新一次评测的 JSON 中产生可见的 fingerprint 差异，无需开发者纪律。
- fingerprint 必须是确定的、跨平台稳定的（同一段代码在 macOS / Linux / Python 3.10 / 3.12 下输出一致）。
- 历史报告读取不受影响——新字段必须可选，缺省时按"未知 fingerprint"处理。

**非目标：**

- **不**对 Judge 做模块化重构（不把 patterns 移到 yaml；那是话题 3 治理范畴）。
- **不**记录 fingerprint 对应的 git commit hash（开发期不可靠：本地未提交修改也算 dirty）。
- **不**为 Adapter / Reporter 做同等指纹（Adapter 的 yaml config 已被 config_snapshot 捕获；Reporter 不影响 verdict 数据）。

## 决策

### 决策 1：哈希什么？

对每个 Judge 收集"会影响判分输出的所有静态属性"，序列化后 sha1 取前 12 位。具体清单（按 Judge 类型）：

| Judge | 进入指纹的内容 |
|-|-|
| `HardGateJudge` | `_EMERGENCY_PATTERNS` + `_REFERRAL_PATTERNS` + `_DOSAGE_PATTERN.pattern` + `_FREQ_PATTERN.pattern` + `_DIETARY_CONTEXT_WORDS` + `_DRUG_CONTEXT_WORDS` + `_DIAGNOSIS_PHRASES` + `_DISCLAIMER_PATTERNS` |
| `RuleJudge` | `_normalize` 函数源码 + `self.normalize`（实例配置） |
| `LLMJudge` | `_PROMPT_TEMPLATE` + `self.model` + `self.temperature` + `self.dual_judge` + `self.second_model` |

序列化方式：把上述对象 dump 成 `json.dumps(..., sort_keys=True, ensure_ascii=False)` 然后 sha1。

**替代方案 A**：直接对模块文件 `__file__` 的源码做 hash。否决：模块改注释也会变，过度敏感。
**替代方案 B**：每个 Judge 手维护 `VERSION = "v2"`。否决：靠纪律，话题原文已讨论。

### 决策 2：fingerprint 是 Judge 实例方法还是类方法？

实例方法 `def fingerprint(self) -> str`。理由：`LLMJudge` 与 `RuleJudge` 的部分指纹依赖实例配置（model、normalize 等）；HardGate 的指纹纯静态，实例方法也无副作用。

### 决策 3：fingerprint 字段放在哪几处？

- **每条 verdict 上**（`JudgeVerdict.judge_fingerprint`）：粒度最细，可在人审界面"按 fingerprint 过滤"。
- **RunReport 顶层**（`judge_fingerprints: dict[name, fingerprint]`）：粒度粗，diff_runs 直接用这层做"是否同 judge"判断。

二者冗余但代价极小（每个 verdict 多 12 字节 string）。

### 决策 4：diff_runs 见到 fingerprint 不一致时做什么？

不阻止 diff，但在输出 Markdown 顶部增加显眼提示块：

```
> ⚠️ Judge 版本不一致：
> | judge | 当前 | 上版本 |
> |-|-|-|
> | hard_gate | a3f1c2 | b7e2d8 |
> | rule      | (相同) | (相同) |
>
> 以下 regression/improvement 列表可能包含"判分变化"导致的伪差异。
```

regression / improvement 列表照常列出，但增加注释提示真因素可能在 judge 改动。

### 决策 5：历史报告兼容性

`JudgeVerdict.judge_fingerprint` 用 `Field(default="")` 默认空字符串；`RunReport.judge_fingerprints` 用 `Field(default_factory=dict)`。Pydantic v2 反序列化历史 JSON 时不会因缺字段失败。`diff_runs` 看到任一侧 fingerprint 为空时输出 "未知 (历史报告)" 而非具体 hash。

## 风险 / 权衡

- **风险**：fingerprint 算法实现 bug 会导致全部历史报告判定为"不一致"。
  **缓解**：单测覆盖（1）一致性：同一段代码两次调用返回相同 hash；（2）敏感性：改任一 pattern 内容必须改变 hash；（3）稳定性：序列化 dict 时 sort_keys 保证跨 Python 版本一致。

- **权衡**：HardGate 指纹覆盖到所有 `_PATTERNS`，但**关键词表的"含义注释"改了不会让 fingerprint 变**。这是预期的——注释不影响匹配。

- **风险**：LLMJudge 的 `_PROMPT_TEMPLATE` 含 `{user}` / `{reply}` 占位符。如果把占位符也算进 hash 没问题（它们是模板字面值的一部分）。

- **风险**：未来若把 `_EMERGENCY_PATTERNS` 拆到 yaml 外置（话题 3 方案 C），fingerprint 需要适配读取 yaml。
  **缓解**：把 fingerprint 计算逻辑作为 Judge 自身的方法，由 Judge 决定哪些内容进 hash；外置后 hash 也外置，调用方无感知。

### 决策 6：fingerprint 取 sha1 前 12 位

具体长度定为 **12 位 hex (48 bit)**。

理由：

- 碰撞概率粗算（生日悖论近似）：50 个 Judge 版本下 ~50²/(2·2^48) ≈ 4e-12，远低于实际风险。
- 报告 Markdown / diff 警告块要被人在一瞥之间扫读，`a3f1c2` 比 `a3f1c2d4e5f6` 可读性更高。
- 若未来真发生碰撞或扩展到多产品线共享 fingerprint，可独立提案升至 16 位（向后兼容：旧报告中 12 位前缀仍可识别）。

### 决策 7：硬编码已知 fingerprint 单测作为漂移保护

`tests/test_judge_fingerprint.py` 必须**硬编码**当前各 Judge 在默认配置下的 fingerprint 字符串字面量。任何对 patterns / prompt / 算法的修改都会让该单测 fail，强制开发者主动 review + 同步更新 CHANGELOG（与 govern-hard-gate-heuristics 提案的 CHANGELOG 机制咬合）。

示例：

```python
def test_known_fingerprints():
    """漂移保护：改了 patterns 必然 fail; 强制 review + 改 CHANGELOG."""
    assert HardGateJudge().fingerprint() == "a3f1c2d4e5f6"
    assert RuleJudge(normalize=True).fingerprint() == "789abcdef012"
    assert LLMJudge(model="gpt-4o-mini", temperature=0.0).fingerprint() == "..."
```

这把"fingerprint 算法稳定性"这件难以靠 review 看出的隐性问题，转化为"任何改动必须显式更新单测"的可见动作。

## Open Questions

- 是否在 CLI 启动时默认输出当前 fingerprint 表？倾向"默认打、可 `--quiet` 静音"，但具体怎么和现有 `logging.INFO` 协调（避免污染 CI 输出）需要在实现时确认。
