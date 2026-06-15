## Context

四模块评分是报告层的叠加产物（`reporter/scoring.py::apply_grading`），在 `build_report` 聚合各维度通过数**之前**运行。这给了我们一个干净的切入点：评分算完后立即据综合分重定义 `overall_passed`，后续聚合自然按新口径统计，无需改 judging/voting 链路。

## Goals / Non-Goals

**Goals**
- 通过/失败 = 综合分是否达满分 1.0（单一、可解释的口径）。
- 关键词标记只保留 `【】` 纯文本一种风格，飞书/Excel 通用。

**Non-Goals**
- 不改 judging 层 per-run `overall_passed` 的定义（仍为 `HardGate AND Rule AND 无错`），它服务于 N-runs majority voting 与 stability 判定。
- 不调整 `config.yaml` 的 `thresholds` 默认值（口径变严是预期内的，由用户按需配置）。
- 不改四模块的分值算法（沿用 `add-weighted-scoring-and-grading`）。

## Decisions

### 决策 1：在 `apply_grading` 里据综合分重定义 `overall_passed`

`apply_grading` 写完 `composite_score` 后置：

```python
r.overall_passed = (
    r.trace.error is None and r.composite_score is not None and r.composite_score >= 1.0
)
```

综合分经 `round(..., 4)`，四模块全满恰为 `1.0`，用 `>= 1.0` 判定稳健。`trace.error` 非空（adapter 全部重试失败）显式判失败，不依赖「错误用例综合分恰好 <1.0」的隐式行为。

**为何不下沉到 judging 层**：综合分依赖 LLM/体验维度，只在折叠后的代表性 trace 上算一次，没有逐 run 综合分。把通过/失败下沉会破坏 voting/stability。因此把「非满分即失败」严格限定在报告层。

### 决策 2：stability 与 overall_passed 解耦，各表一义

报告层重定义后会出现 `overall_passed=False` 但 `stability=stable_pass` 的组合（确定性检查每轮都过、只是没拿满分）。这是**刻意保留**的：
- `overall_passed`（报告层）度量「这次表现是否满分」；
- `stability`（judging 层）度量「确定性检查的运行一致性 / 抖动」。

在 spec、`models.py` 注释与知识库中显式说明二者口径不同，避免读者误读概览表。

### 决策 3：关键词标记只留 `【】`，删除 `red` 富文本

`write_transcripts_xlsx` 移除 `highlight` 形参；`_turn_cell` 移除 `red` 分支与 `CellRichText/TextBlock/InlineFont` 导入。命中关键词一律走 `_mark_plain` → `【关键词】`。理由：飞书 xlsx 导入丢弃富文本单元格，`red` 对主用法无效且需额外维护一条本地专用产物路径。

## Risks / Trade-offs

- **风险**：`thresholds.overall_pass_rate`（默认 0.85）在新口径下要求 85% 用例满分，CI 门禁会显著变严，几乎必然触发非零退出。**缓解**：在 proposal/知识库中明确提示，门禁强度由 `config.yaml` 控制；本变更不动默认值，交由用户决定。
- **权衡**：`overall_passed` 字段语义在报告层被「改写」，与 judging-pipeline 规格里的定义口径不同。**缓解**：judging-pipeline 规格加交叉引用说明「报告层会重定义」，reporting 规格承载最终口径。

## Migration Plan

无数据迁移。历史 `report.json` 字段不变、仍可加载；重新跑评测即按新口径产出。`openpyxl` 依赖版本不变。

## Open Questions

- 是否需要把 `thresholds.overall_pass_rate` 默认值随新口径下调（例如改为度量「评级合格率」而非「满分率」）？本变更暂不处理，留待门禁口径单独讨论。
