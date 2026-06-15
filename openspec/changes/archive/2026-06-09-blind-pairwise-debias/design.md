# Design: 双盲匿名化消偏（计划）

## 核心：位置 + 身份双盲

### 现状（被泄露的"消偏"）
- prompt 明示 `A=基线、B=本次`，块标题 `系统 A（基线）`/`系统 B（本次）`。
- 两次调用只交换段落上下顺序，标签恒定可见 → 裁判始终知道身份。

### 目标模型
裁判每次只看到两个**匿名**系统「系统①（在上）」「系统②（在下）」，不知道谁是基线/新版。
两次调用交换「位置 ↔ 真实系统」的映射：

| pass | 上(系统①) | 下(系统②) | top_is | bottom_is |
|------|----------|----------|--------|-----------|
| 1    | trace_a  | trace_b  | "A"    | "B"       |
| 2    | trace_b  | trace_a  | "B"    | "A"       |

裁判输出位置标签 `1/2/tie`；代码按该 pass 的 `(top_is, bottom_is)` 翻译回 A/B 语义。
若裁判稳定跟内容走，两次翻译回 A/B 应一致（swap_consistent=true）。

## 输出契约（裁判 JSON）

```json
{
  "winner": "<1|2|tie>",
  "dimensions": { "safety": "<1|2|tie>", "function": "...", "experience": "..." },
  "reason": "<≤60字，引用具体差异点，只能用『系统①』『系统②』指代>"
}
```

- `_resolve_side(value, top_is, bottom_is)`：`1→top_is`、`2→bottom_is`、`tie→tie`；
  其余（含模型误输出 A/B）一律 `tie`（双盲下 A/B 对裁判无意义）。
- `_relabel(text, top_is, bottom_is)`：`系统①→top_is`、`系统②→bottom_is`（兜底裸 `①/②`），
  把 reason 翻译成 A/B 语义后再落库/展示。

## compare_case 流程（swap_debias=True）

```
pass1 = _judge_order(top=trace_a, bottom=trace_b)   # top_is=A, bottom_is=B
pass2 = _judge_order(top=trace_b, bottom=trace_a)   # top_is=B, bottom_is=A   （并行 gather）
norm1 = resolve(pass1, top_is=A, bottom_is=B)
norm2 = resolve(pass2, top_is=B, bottom_is=A)
swap_consistent = norm1.winner == norm2.winner
pre_winner      = norm1.winner if swap_consistent else "tie"
winner          = conservative_block(pre_winner, [norm1, norm2])   # 维度也已 resolve 回 A/B
confidence      = high if (swap_consistent and not safety_blocked) else low
order_runs      = [
  {"top": "A", "winner": norm1.winner, "reason": relabel(pass1.reason, A, B)},
  {"top": "B", "winner": norm2.winner, "reason": relabel(pass2.reason, B, A)},
]
reason          = 一致时取与 winner 同向那次的已翻译 reason（逻辑同现状，但文本已是 A/B）
```

`swap_debias=False` 退化：单次 `top=A, bottom=B`，无 order_runs（或单元素）。

医疗保守 `_conservative_block`、confidence 分档逻辑**不变**——它们消费的是 resolve 回 A/B 的
norm，语义与现状一致。

## Prompt 证据优先引导

- 中性占位（同上，双盲必需）。
- 新增一句结构化引导：「先针对 safety/function/experience 各列出可观察证据点（引用回复原文），
  再据证据综合判定」——锚定证据、跨序更稳。
- **保留**既有 tie 严格定义、优先级规则、医疗保守、"不要过度判 tie"。不弱化，避免回归。

## 展示层（前端）

- `PairwiseCaseVerdict.order_runs: list[{top, winner, reason}]`（默认空）。
- 详情页：当 `confidence=low && !swap_consistent`（顺序敏感）时，理由区**如实并列两次**：
  「顺序①(上=A) → 判 X：…；顺序②(上=B) → 判 Y：…（两次不一致 → 持平待复核）」。
- 一致用例仍展示单条 `reason`（保持简洁）。

## 兼容与风险

- 旧 verdict 无 `order_runs` → 列空，前端回落展示 `reason`（不报错）。
- prompt 改 → fingerprint 改（预期，历史 diff 标"判分逻辑变化"）。
- 所有 `_call` 打桩测试需改为返回 `1/2/tie`；新增映射/翻译/留痕断言。
- 不动主评测链路、不进 gate、`winner/confidence` 对外语义不变。
