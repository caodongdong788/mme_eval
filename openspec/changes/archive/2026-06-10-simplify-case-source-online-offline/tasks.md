# Tasks

## 1. 测试
- [ ] 1.1 loader 测试：`source: offline` 合法；旧值 `expert_crafted` 加载失败。

## 2. 实现
- [ ] 2.1 改 `Source` 枚举与默认值为 `offline`。
- [ ] 2.2 批量更新 71 条用例 YAML。
- [ ] 2.3 更新 tests/factories、文档。

## 3. 验证
- [ ] 3.1 pytest 全绿；`medeval validate`；dry-run。
- [ ] 3.2 graphify update；openspec archive。
