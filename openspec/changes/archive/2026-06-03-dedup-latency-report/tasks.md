# Tasks

## 1. 测试先行（TDD）
- [x] 1.1 `diff_summary` 含「性能变化」块 → `render_markdown` 输出 MUST NOT 含独立「## 性能（仅记录）」段
- [x] 1.2 无 diff / diff 无性能块 → MUST 含独立「## 性能（仅记录）」段（兜底）
- [x] 1.3 `_latency_diff` 表头第四列为「变化」，不再是「Δ」

## 2. 实现
- [x] 2.1 `markdown_report.render_markdown`：`"性能变化" in diff_summary` 时跳过独立 latency 段
- [x] 2.2 `diff._latency_diff`：表头 `Δ` → `变化`

## 3. 验证
- [x] 3.1 全量 `pytest` 绿（331 passed）
- [x] 3.2 真实 config `medeval run --config config.yaml --dry-run` 通过
- [x] 3.3 `graphify update .` 刷新图谱
- [x] 3.4 `openspec validate --strict` 通过并归档
- [x] 3.5 真实报告重渲染验证：性能变化块在、底部独立段消失、列名为「变化」
