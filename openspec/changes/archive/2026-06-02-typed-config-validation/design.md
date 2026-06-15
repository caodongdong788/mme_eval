# Design — config 全量类型化校验

## 目标与约束

- **单一真值源**：配置层的字段、取值约束、跨字段规则集中在 `medeval/config.py`。
- **fail-fast**：拼错/多余字段、类型错、跨字段非法在**加载期**报错，而非运行中或静默。
- **判分零回归**：合法 config 的行为/判分结果完全不变。
- **改动半径可控**：scoring / reporter / diff / excel 不动（见下"scoring 决策"）。

## 模型结构（`medeval/config.py`）

```
Config(extra=forbid)
├─ run: RunCfg            name str, description str="", output_dir str="outputs",
│                         concurrency int=4, timeout_s float=90, retry int=2, repeat int>=1 =1
├─ cases: CasesCfg        include list[str]=[], exclude list[str]=[], tags list[str]=[]
├─ adapter: AdapterCfg    type: Literal[http,openai_compat,openai,doubao,ark]
│   ├─ openai_compat: OpenAICompatCfg | None
│   └─ http: HttpCfg | None
│   (model_validator: type=http → http 必填；type∈compat 系 → openai_compat 必填)
├─ judges: JudgesCfg
│   ├─ hard_gates: HardGatesCfg(enabled=True)
│   ├─ rule: RuleCfg(enabled=True, normalize=True, semantic_adjudicator: SemanticAdjudicatorCfg)
│   ├─ scoring_point: ScoringPointCfg(LLM 字段 + self_consistency>=1)
│   └─ llm: LLMJudgeCfg(LLM 字段 + dual_judge/second_model/self_consistency/aggregate)
├─ reporter: ReporterCfg  formats list[str]=["markdown"], diff_against str="", lark: LarkCfg
├─ thresholds: ThresholdsCfg   各 *_pass_rate: float|None（全可选）
└─ scoring: ScoringCfg
    ├─ module_max: dict[str,float]={}（自由叶子；数值默认归 scoring.py）
    ├─ function_deduction: float|None
    ├─ grade_thresholds: dict[str,float]={}
    ├─ pass_rule: Literal["perfect"] | ThresholdRule | None
    ├─ profiles: dict[str, ProfileCfg]={}      （名字自由；ProfileCfg extra=forbid）
    └─ profile_match: list[ProfileMatchCfg]=[]  （WhenCfg extra=forbid）
```

LLM 字段公共集（semantic_adjudicator / scoring_point / llm 共享）：`enabled bool`、
`provider Literal[openai,azure]`、`model str`、`api_key_env str`、`api_key str=""`、
`base_url str=""`、`api_version str=""`、`default_headers dict[str,str]={}`、`temperature float=0.0`。
azure 跨字段校验：`provider=azure` → `base_url` 与 `api_version` 非空。

`OpenAICompatCfg` / `HttpCfg` 的字段集**严格对齐 adapter 构造函数**（含可选 `timeout_s`），
保证 `build_adapter(type, config.adapter.model_dump())` 里 `Adapter(**dump[type])` 不会因多/缺 kwarg 失败。

`pass_rule`：`ThresholdRule(extra=forbid)`：`type: Literal["threshold"]="threshold"`、
`min_composite: float`、`gates: dict[str, Literal["full"]]={}`（dim 名自由、gate 值限 "full" 抓笔误）。

## 分区 forbid 的边界

- **forbid（抓拼错）**：所有 `*Cfg`（结构化节点）。`adaptor:`、`self_consistensy:`、`provdier:` 等加载即报错。
- **宽松（dict 叶子）**：`default_headers` / `extra_body` / `http.headers` / `module_max` / `grade_thresholds` / `gates`（键自由）、`profiles` 的**名字**自由。
- 每个 profile 的**内部字段** forbid（小固定集 module_max/function_deduction/grade_thresholds/pass_rule），抓 profile 内笔误——已与用户确认。

## scoring 决策（关键风险规避，偏离初版设计并说明理由）

初版设计提过把 `resolve_profile/score_case` 改吃 `ScoringCfg`（typed 合并）。实现期发现其
**真实输入来自 `config_snapshot["scoring"]`**（`reporter/aggregator.build_report` 与
`reporter/excel_transcript` 都从已序列化的 snapshot dict 取 scoring），若强行改 typed 需在两个
reporter 调用点重建 `ScoringCfg`，并重写判分最敏感、测试最重的 dict 合并逻辑——**纯增风险、零增安全**
（拼错已在加载期被 `Config` 拦截）。

故定稿：**scoring.py 维持 dict 接口**。`Config.ScoringCfg` 只负责"结构校验 + 禁拼错 + pass_rule 形状"，
**不复制数值默认**（module_max/扣分步长/阈值的数值默认仍由 `scoring.py` 的 `DEFAULT_*` 独占），
从根上消除双默认源。这样既达成"单一真值源 + 加载即 fail-fast"，又把判分回归风险降到 0。

## CLI override 与校验顺序

`run` 支持 `--run-name/-a adapter/-t tags` 覆盖。为保证覆盖也走校验：
`_load_config` 读 yaml → `Config.model_validate`（友好报错）→ 返回 typed `Config`；
`run()` 在 typed 对象上应用覆盖（`config.run.name=...` / `config.cases.tags=...` / `config.adapter.type=...`）。
`adapter.type` 覆盖后由 `build_adapter` 既有 fail-fast 兜底（极少用）。

## 友好报错

`load_config` 捕获 `pydantic.ValidationError`，逐条渲染 `<loc 点路径>: <msg>`（如
`judges.llm.self_consistensy: Extra inputs are not permitted`），以 `click.UsageError`/非零退出，
不抛原始 traceback。`medeval validate` 一并享受。

## 测试

- `tests/test_config.py`：
  - 现网 `config.yaml` 合法通过；
  - 顶层/judges/scoring 拼错字段被拒（forbid）；
  - 类型错（concurrency 填字符串、provider 非法枚举、aggregate 非法）被拒；
  - 跨字段错（azure 缺 base_url/api_version、adapter.type 与子块不匹配）被拒；
  - 默认值填充正确；
  - 自由叶子（default_headers/extra_body/profiles 名字）允许额外键；
  - pass_rule 三种写法（缺省/"perfect"/threshold dict）都能解析。
- scoring 无改动 → 现有 scoring/grading 测试套即回归基线。
- 全量 pytest + `verify-heuristics` + 真实 1-case run 判分对拍。
