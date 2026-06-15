## 1. 删除 HTML reporter

- [x] 1.1 删除 `medeval/reporter/html_report.py`
- [x] 1.2 删除 `templates/report.html.j2`
- [x] 1.3 `medeval/reporter/__init__.py` 删除 `from .html_report import write_html` 与 `__all__` 暴露

## 2. CLI 改造

- [x] 2.1 `medeval/cli.py` 删除 `if "html" in formats: write_html(...)` 整段
- [x] 2.2 `medeval/cli.py` 把 JSON 写盘从 `if "json" in formats:` 守卫中移出，改为无条件 `write_json` 在 reporter 入口处先写
- [x] 2.3 `medeval/cli.py` formats 默认值从 `["html","markdown","json"]` 改为 `["markdown"]`
- [x] 2.4 `medeval/cli.py` 在 case 加载前 fail-fast 校验 raw_formats：含 `"html"` → `click.UsageError` 退出；含 `"json"` → console warning 并从列表移除
- [x] 2.5 `medeval/cli.py` 飞书发布的 `lark_cfg.get("enabled")` 改成 `lark_cfg.get("enabled", True)`，未显式配置时按 true 处理；显式 `enabled: false` 时跳过

## 3. 配置文件 / 历史快照

- [x] 3.1 `config.yaml` / `config.l1.yaml` / `config.multi_turn.yaml`：`formats` 改为 `["markdown"]`；`config.yaml` 上加注释说明"html 已下线、json 始终写盘"；`reporter.lark.enabled` 留显式 `true`（默认开但显式更安全）
- [x] 3.2 历史 `outputs/*/report.html` 不动（保留作历史快照）

## 4. 测试改造

- [x] 4.1 删除 / 重写 HTML 渲染测试：grep 已无 `from medeval.reporter.html_report` / `write_html`
- [x] 4.2 新增 `tests/test_report_formats_default.py::test_default_outputs_md_and_json`：默认 config 跑一遍，断言 `report.md` + `report.json` 存在、无 `report.html`
- [x] 4.3 同文件 `test_empty_formats_still_writes_json`：`formats: []` 时 json 仍写、md 不写
- [x] 4.4 同文件 `test_formats_html_is_rejected`：`formats: ["html"]` 必须立即 fail-fast；`test_json_in_formats_is_warned_and_ignored` 验证 json warning

## 5. Docs / Spec

- [x] 5.1 README "快速开始" 中 `open outputs/<run>/report.html` 改为 `report.md` / `report.json` / `lark_url.txt`
- [x] 5.2 grep `report\.html|write_html` 已无代码侧引用
- [x] 5.3 `openspec/specs/reporting/spec.md` 主 spec 合入：删除 "HTML 报告" 需求 + 场景，新增 "JSON 无条件写盘"、"formats 只接受 markdown" 需求 + "飞书默认开" 场景；设计原则改为"二态输出"

## 6. 端到端验证

- [x] 6.1 测试覆盖等价场景（无需真实 chatbot 跑 multi_turn）：`test_default_outputs_md_and_json` 验证 md+json 都生成、html 不生成
- [x] 6.2 `test_formats_html_is_rejected` 验证 `formats: ["html"]` 报错退出，错误消息包含 "html" 与 "trim-report-formats" / "下线"
- [x] 6.3 `pytest tests/ -q` 全过：70 用例（新增 4，删除 0）
- [x] 6.4 `openspec validate trim-report-formats --strict` 通过

## 7. 归档

- [x] 7.1 [人工触发] PR review 通过、合入主干后运行 `/opsx-archive-change`
