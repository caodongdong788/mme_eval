## 1. 删除 MockAdapter 代码

- [x] 1.1 删除 `medeval/adapter/mock.py` 整文件
- [x] 1.2 `medeval/adapter/__init__.py` 中删除 `from .mock import MockAdapter`、`__all__` 暴露、`build_adapter` 中 `if adapter_type == "mock"` 分支
- [x] 1.3 `medeval/adapter/__init__.py::build_adapter` 在 `adapter_type` 为 `""` / None / 不识别时改为 `raise ValueError("config.adapter.type is required ...")`，错误消息列出已支持类型
- [x] 1.4 `medeval/cli.py` 中两处 `adapter_cfg.get("type", "mock")` 改为 `adapter_cfg.get("type", "")`；CLI 把 `ValueError` 包成 `click.UsageError` 给友好报错而非 traceback

## 2. Models 默认值

- [x] 2.1 `medeval/models.py::RunReport.adapter_type` 字段：默认值由 `"mock"` 改为 `""`（无新增校验器；空串语义已通过 fail-fast 在 build_adapter 层面拦截）
- [x] 2.2 历史 mock-generated report.json 仍可加载（`adapter_type=="mock"` 不抛错）；`diff_runs` 已加 `_mock_baseline_warning`，对比双方任一为 mock 时输出 "⚠️ 非可信基线" 警告

## 3. 测试改造

- [x] 3.1 `tests/test_smoke.py` 已用 in-test `_FakeAdapter`（继承 BaseAdapter）替代下线的 MockAdapter；按 behavior 返回固定回复，覆盖 "adapter → runner → judge" 全链路而无需 httpx_mock 这种额外依赖（更轻、更直观）
- [x] 3.2 `pytest tests/test_smoke.py -v` 0.6s 跑完，0 mock 依赖
- [x] 3.3 grep `MockAdapter|adapter: mock|type: \"mock\"` 仅在 OpenSpec change 文档里残留（这是预期，作为变更记录），代码侧已全部清除

## 4. Config / Skill / Docs 清理

- [x] 4.1 删除 `config.multi_turn_smoke.yaml`
- [x] 4.2 `config.yaml` 删除 `adapter.mock` 子节点；README 把 "用 Mock Adapter 跑通流程" 改成 "配好你的 chatbot adapter 后跑评测"
- [x] 4.3 `.cursor/skills/` grep 无 mock 残留

## 5. Spec 更新

- [x] 5.1 已把 chatbot-adapter spec delta 合入主 spec `openspec/specs/chatbot-adapter/spec.md`：删除 "MockAdapter" 需求 + 3 个场景，新增 "fail-fast 拒绝缺失 adapter type" 需求 + 3 个场景；`build_adapter` 工厂需求也同步移除 `mock` 字眼
- [x] 5.2 `rg "Mock|mock" openspec/specs/` 已清空（仅 change 历史保留）
- [x] 5.3 `openspec validate drop-mock-adapter --strict` 通过

## 6. 端到端验证

- [x] 6.1 用空 `adapter: {}` 的 config 跑 `medeval run` → 退出码 2，stderr 含 "Error: config.adapter.type is required..."，friendly 提示，无 traceback
- [x] 6.2 现有 `config.l1.yaml` / `config.multi_turn.yaml` 不变（adapter.type 已是 openai_compat），行为完全一致
- [x] 6.3 `pytest tests/ -q` 全过（66 用例）

## 7. 归档

- [x] 7.1 [人工触发] PR review 通过、合入主干后运行 `/opsx-archive-change`
