## 1. 模型与配置

- [x] 1.1 在 `medeval/models.py` 新增 `ScoringPoint` model（`criterion`/`points:int`/`guideline:str=""`/`critical:bool=False`），校验 `points != 0`
- [x] 1.2 在 `TestCase` 增加 `scoring_points: list[ScoringPoint] = Field(default_factory=list)`（向后兼容）
- [x] 1.3 在 `CaseResult`/`RunReport` 增加指南匹配率派生字段（如 `guideline_match_rate: float | None`、聚合 counter），默认值兼容历史 report.json
- [x] 1.4 在 `config.yaml` 的 `judges` 下新增 `scoring_point` 段：`enabled`(默认 true)、`provider`、`model`、`api_key_env`/`api_key`、`base_url`、`api_version`、`temperature`

## 2. ScoringPointJudge 核心

- [x] 2.1 新建 `medeval/judges/scoring_point.py`，定义 `ScoringPointJudge`（复用 LLMJudge 的 client 构建与指数退避重试）
- [x] 2.2 设计逐点判定 prompt：输入完整对话 + 得分点列表（criterion），输出严格 JSON `[{met:bool, reason:str}, ...]`
- [x] 2.3 实现归一化得分（含负分语义与 `max_positive==0` 边界）；verdict 填 `score=achieved`、`max_score=max_positive`
- [x] 2.4 空 `scoring_points` 直接返回空列表、零 API 调用；grader 失败降级为"全部未命中"verdict 不崩溃
- [x] 2.5 实现 `fingerprint()`：覆盖 prompt 模板 + provider + model + temperature，不覆盖得分点内容

## 3. 接入判分与聚合

- [x] 3.1 在 `medeval/judges/__init__.py` 导出 `ScoringPointJudge`
- [x] 3.2 在 `aggregator` 将 `scoring_point.*` 归入软分（`soft_score`/`soft_score_max`），不参与 `hard_gate_passed`/`overall_passed`
- [x] 3.3 在 `aggregator` 从带 `guideline` 锚点的得分点派生用例级指南匹配率（按点计数，无锚点记 N/A 不计入分母）
- [x] 3.4 在 `medeval/cli.py` 构建 `ScoringPointJudge` 并接入判分循环；N-runs 下只对代表性 trace 调用一次（与 LLM judge 一致）
- [x] 3.5 在 `_print_judge_fingerprints` 纳入得分点判官 fingerprint

## 4. 报告呈现

- [x] 4.1 在 markdown 报告为含得分点用例渲染逐点命中明细（描述/分值/命中状态/负分标注）
- [x] 4.2 在报告单独切片指南匹配率，明确标注"仅度量、未设否决"，与 HardGate 通过率分开

## 5. 用例与测试

- [x] 5.1 为 `bc_screen_birads3` 等样例 case 补 `scoring_points`（含正分、负分、guideline 锚点）做示范
- [x] 5.2 单测：空得分点零调用；正负分归一化（含 `max_positive==0` 边界）；grader 失败降级
- [x] 5.3 单测：`scoring_point.*` 软分不影响 `overall_passed`；历史无得分点用例软分语义不变
- [x] 5.4 单测：指南匹配率按点计数派生、无锚点记 N/A、不否决
- [x] 5.5 单测：fingerprint 覆盖 prompt/model/temperature、不随得分点内容变化；改 prompt 触发变化
- [x] 5.6 运行 `medeval verify-heuristics` 确认 HardGate 治理三检不受影响
