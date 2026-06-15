# Tasks

## 1. Schema
- [x] 1.1 新增 `medeval/config.py`：全量 `Config` 模型（run/cases/adapter/judges/reporter/thresholds/scoring）+ 分区 forbid + 跨字段 model_validator（adapter.type↔子块、azure 必填 base_url/api_version、pass_rule 形状）
- [x] 1.2 `OpenAICompatCfg`/`HttpCfg` 字段严格对齐 adapter 构造函数（含可选 timeout_s）
- [x] 1.3 `load_config(path) -> Config`：yaml→model_validate，捕获 ValidationError 渲染友好键路径报错并非零退出

## 2. TDD 测试
- [x] 2.1 `tests/test_config.py`：合法 config.yaml 通过 / 拼错被拒 / 类型错被拒 / 跨字段错被拒 / 默认值 / 自由叶子放行 / pass_rule 三写法（19 条）

## 3. 接线
- [x] 3.1 `cli._load_config` 返回 `Config`；`run/validate/list-cases` 改吃 typed
- [x] 3.2 `_build_judges(config.judges)` / `_build_adjudicator(config.judges)` 接 typed
- [x] 3.3 `build_adapter(config.adapter.type, config.adapter.model_dump())`；CLI override 在 typed 对象上应用
- [x] 3.4 `_check_thresholds(report, config.thresholds)` 接 typed（保留历史缺省口径）
- [x] 3.5 `RunReport.config_snapshot = config.model_dump(mode="json")`

## 4. 验证
- [x] 4.1 全量 `pytest` 绿：276 passed（+19 test_config）
- [x] 4.2 `medeval verify-heuristics` 通过
- [x] 4.3 真实 1-case `medeval run` 跑通、判分对拍无回归
- [x] 4.4 `medeval validate`：合法 config 通过、拼错 config fail-fast（exit=2，键路径报错）
- [x] 4.5 `graphify update .` 刷新图谱
- [x] 4.6 `openspec validate --strict` 通过并归档
