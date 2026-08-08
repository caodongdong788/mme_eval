# Deduplicate Case Image Markdown

## Goal

- Case 图片已作为附件展示时，不再显示正文中的图片 Markdown 与相对路径。
- CX 原生回放和 MME 本地回放保持一致。
- 普通文本及未作为附件加载的 Markdown 图片维持原行为。

## Verification

- Adapter 测试覆盖带换行的图片 Markdown 清理与图片字段发送。
- 前端测试覆盖附件图片只展示一次，正文不出现路径。
