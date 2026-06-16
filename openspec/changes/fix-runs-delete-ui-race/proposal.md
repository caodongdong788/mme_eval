# Proposal: 评测列表删除后 UI 不即时消失

## Why

删除评测成功后，3s 轮询的 `reload()` 可能与 `onDelete` 内的 `reload()` 竞态，旧 HTTP 响应覆盖乐观更新，行需手动点「刷新」才消失。

## What

- `onDelete` 开始时递增 `reloadSeq` 作废进行中的 `reload`
- 删除成功仅做乐观 `setRuns` 过滤，不再 `await reload()`（与 Pairwise 删除一致）
- 删除失败时 `reload()` 重新对齐服务端
