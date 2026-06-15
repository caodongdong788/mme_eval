# Proposal: 前端 DRY 优化（标签缓存 / YAML 打开 / Pairwise）

## What Changes

- 抽 `useConfigLabelMap` 统一 `failureTags` / `judgeVerdictLabels` 缓存逻辑
- 抽 `useYamlEditorState` 合并 `useCaseDetail` / `useRunDashboard` 的 YAML 加载
- `usePairwisePage` 改用 `useAsyncData`；`usePairwiseExpandedMessages` 带缓存并行拉取
- 删除仅 Pairwise 使用的 `useCaseMessages.ts`

## Non-Goals

- 后端 rejudge 下沉、`api.ts` shim 批量迁移
