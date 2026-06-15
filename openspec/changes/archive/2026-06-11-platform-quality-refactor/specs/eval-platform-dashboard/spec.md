## ADDED Requirements

### Requirement: 取数失败的错误兜底状态

看板各页面在调用后端接口失败时 SHALL 渲染明确的错误兜底状态（如错误提示与重试入口），MUST NOT 因为请求失败而停留在永久加载（无限 loading）状态。详情类页面（run 详情、用例详情、pairwise 详情）在目标资源不存在或加载失败时 MUST 给出可读的失败提示而非空白或常驻 Spin。

#### Scenario: 详情接口失败不再无限 loading

- **WHEN** 打开某 run/用例详情页且其数据接口返回错误
- **THEN** 页面 MUST 展示错误提示与重试/返回入口，而非持续显示加载占位

#### Scenario: 应用级未捕获错误不白屏

- **WHEN** 某页面渲染抛出未捕获异常
- **THEN** 应用 MUST 由错误边界兜底展示降级界面，而非整页白屏
