# Proposal: 看板用例结果表 UX 调整

## Why

用户在使用"用例结果"表时反馈三处体验问题：列标题语义不清（"子场景/场景"易混淆）、"仅看待审"会把
已审用例也算进来导致重复审、缺少按人审结论快速过滤、固定列宽导致表头拥挤换行。本次为前端 UX 调整，
不涉及判分内核与后端契约（复用既有 `review` 字段）。

## What Changes

- 列标题重命名：「子场景」→「场景描述」，「场景」→「类别」（仅展示文案，dataIndex 不变）。
- 「仅看待审」语义收紧：MUST 只展示在审核队列内且**尚未有人审结果**的用例（已裁定的移出待审视图）。
- 新增「人审结果」筛选：可按 同意 / 推翻 / 未审 过滤，且与其它筛选叠加；该筛选按 run 维度随筛选条件一并记忆。
- 用例结果表列宽 MUST 自适应内容（`tableLayout=auto`、去除固定 width），避免表头拥挤换行。

## Impact

- Affected specs: `eval-platform-dashboard`。
- Affected code: `frontend/src/pages/RunDashboardPage.tsx`（纯前端）。
- 判分内核 `medeval/**` 与后端契约零改动。
