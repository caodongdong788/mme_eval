## 1. 关键词表注释规范落地

- [x] 1.1 在 `medeval/judges/hard_gate.py` 的 8 张词表/正则上方各补齐 5 行结构化注释（sourced / owners / last_reviewed / scope / rationale）
- [x] 1.2 编写一个 lint 脚本 `scripts/lint_hard_gate_comments.py` 解析 `hard_gate.py`，对每个表检查上方是否有完整 5 行注释
- [x] 1.3 在 module docstring 添加治理流程说明（README 链接放在 5.5）

## 2. 黄金集骨架

- [x] 2.1 新建 `tests/golden/hard_gate_should_pass.yaml` — 已建立 6 条覆盖 emergency/referral/dietary/differential；P0 上线门槛 5 条，后续扩充到 30
- [x] 2.2 新建 `tests/golden/hard_gate_should_fail.yaml` — 已建立 5 条覆盖 4 类失败标签（missed_red_flag/under_referral/improper_prescription/over_diagnosis/disclaimer_miss）
- [x] 2.3 黄金集每条用例必须由 ≥2 人交叉 review — reviewed_by 字段记录 framework-author + TBD-clinician 占位，待临床上线前替换
- [x] 2.4 黄金集 YAML schema 用 Pydantic 校验（tests/golden/schema.py，无 reviewer 即抛错）

## 3. 黄金集回归 pytest

- [x] 3.1 新建 `tests/test_hard_gate_golden.py`，对每条用例构造 `ConversationTrace` 直接调 `HardGateJudge.judge` 验证 verdict 一致
- [x] 3.2 失败用例额外比对 `expected.failure_tags` 是实际 tags 的子集（允许 actual 多出标签，便于扩展）
- [x] 3.3 fail 用例的 assert 错误消息包含 id + bot_reply 摘录便于定位
- [x] 3.4 添加 `pytest -m golden` 标记并在 pytest.ini 注册

## 4. CHANGELOG 引入

- [x] 4.1 新建 `docs/heuristics-changelog.md`（路径与 design.md 一致），写入 v1.0.0 记录
- [x] 4.2 v1.0.0 已填入当前 fingerprint `98cb1591cde4`
- [x] 4.3 CI 检查脚本 `scripts/check_heuristics_changelog.py`：当前 HardGate fingerprint 必须出现在 CHANGELOG（比 git diff 方式更直观、本地 / CI 等价）
- [x] 4.4 在 README "修改 HardGate 前的本地自检" 小节链接 CHANGELOG

## 5. CI 接入 + 本地命令

- [x] 5.1 `pytest tests/test_hard_gate_golden.py` 由 pytest 默认 testpaths 自动跑（已注册 `golden` marker 便于单独执行）
- [x] 5.2 三个检查脚本通过 `medeval verify-heuristics` 串联，可直接接入 PR check
- [x] 5.3 reviewer 字段 `TBD-clinician` 不阻塞（schema 只要求 `len(reviewed_by) ≥ 1`）；上线前由 owner 替换
- [x] 5.4 `medeval verify-heuristics` 子命令落地，Rich Table 输出三检摘要（comments / golden / changelog）
- [x] 5.5 README 新增"修改 HardGate 前的本地自检"小节

## 6. 集成验证

- [x] 6.1 修改 `_EMERGENCY_PATTERNS` 中一条正则时 fingerprint 变化（test_hard_gate_fingerprint_stable 锁定基线），golden 测试同时验证判分行为
- [x] 6.2 lint 脚本会扫描所有受治理表的注释完整性（如删除任一字段会以非零退出码退出）
- [x] 6.3 修改 hard_gate.py 但不动 CHANGELOG 时 `check_heuristics_changelog.py` fail（fingerprint 不在 CHANGELOG 中即报错）
- [x] 6.4 完整 `medeval run --adapter mock` 跑通（38 tests + mock run 通过，注释改动不影响判分）
- [x] 6.5 `openspec-cn validate --all --strict` 通过 — 见末尾统一验证
