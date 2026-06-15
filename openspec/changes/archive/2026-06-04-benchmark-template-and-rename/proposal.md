# Proposal: 内置 benchmark 模板化 + benchmark 改名/描述

## Why

Benchmark 库当前把内置（builtin）benchmark 和用户上传的混在一张表里，内置项的"覆盖/删除"本就禁用、
"上传人"显示"内置"，信息冗余。内置集更像是"用例模板/样例"，应从列表抽离、单独入口展示。
另外用户上传的 benchmark 名称/描述当前不可编辑，改错只能删了重传。

## What Changes

- Benchmark 库列表 MUST 只展示上传（uploaded/派生）benchmark，不再展示内置项。
- 内置 benchmark MUST 以「用例模板」入口形式呈现在"上传 benchmark"按钮左侧，点击可查看其用例。
- 新增 `PATCH /api/benchmarks/{id}` 修改名称与描述；内置 benchmark MUST NOT 可改（与覆盖/删除一致）。
- 列表每条上传 benchmark MUST 提供"编辑"操作，弹窗修改名称/描述。

## Impact

- Affected specs: `eval-platform-service`（benchmark 改名/描述接口）、`eval-platform-dashboard`
  （benchmark 库模板入口与编辑）。
- Affected code: `server/schemas.py`、`server/routers/benchmarks.py`、`frontend/src/api.ts`、
  `frontend/src/pages/BenchmarksPage.tsx`；测试 `tests/server/test_benchmarks_api.py`（或新增）。
- 判分内核 `medeval/**` 零改动。
