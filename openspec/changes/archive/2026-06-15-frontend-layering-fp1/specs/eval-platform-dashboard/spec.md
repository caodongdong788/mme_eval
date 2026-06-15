## MODIFIED Requirements

### Requirement: 前端页面组件化与快照测试

除 Pairwise 域外，Runs / Benchmarks / JudgeModels / Trends / ReleaseThresholds / Launch / CaseDetail 等页面 MUST 将列表取数、轮询与 mutations 收敛至 `frontend/src/hooks/`，优先复用 `useAsyncData` 管理 loading/error/reload；`pages/` 层 MUST NOT 保留裸 `useEffect` + `api.*` 初始加载块（轮询等特殊逻辑可封装在专用 hook 内）。

#### Scenario: CRUD 列表页由 hook 承载取数

- **WHEN** 用户打开评测列表、Benchmark 库、判分模型、趋势或阈值配置页
- **THEN** 初始加载与刷新 MUST 经 hooks 触发
- **AND** 页面文件 MUST 以组合组件与 hook 返回值为主，交互与拆分前一致

#### Scenario: 用例详情由 useCaseDetail 承载

- **WHEN** 用户打开 run 用例详情页
- **THEN** 用例明细、标注、YAML 试判等副作用 MUST 在 `useCaseDetail` 内
- **AND** 错误展示与返回导航行为 MUST 与拆分前一致
