## ADDED Requirements

### Requirement: benchmark 管理界面

前端 SHALL 提供 benchmark 管理页：上传 YAML 用例集、展示 benchmark 列表（含 builtin 与上传项）、查看某 benchmark 的用例清单。上传失败时 MUST 展示后端返回的校验错误。

#### Scenario: 上传并查看 benchmark

- **WHEN** 用户在管理页上传一个合法用例集
- **THEN** 列表中出现该 benchmark，点击可查看其用例清单

### Requirement: 发起评测界面

前端 SHALL 提供发起评测入口：选择 benchmark、配置评测打分模型（judge 的 provider/model/base_url/api_key）、设置 repeat/tags/limit/run_name；提交后跳转或提示评测已进入队列。

#### Scenario: 配置打分模型发起评测

- **WHEN** 用户选定 benchmark、填入 judge 模型参数并提交
- **THEN** 前端调用发起评测 API 并展示新建 run 的运行状态

### Requirement: 评测列表与实时进度

前端 SHALL 展示所有评测 run 的列表（状态、通过率、时间），对运行中的 run MUST 展示实时进度（轮询后端进度接口）。

#### Scenario: 运行中进度更新

- **WHEN** 某次评测处于 running 状态
- **THEN** 列表对应行 MUST 周期性刷新进度，直至 success/failed

### Requirement: 单次评测看板

前端 SHALL 为单次 run 呈现聚合看板：核心指标卡（总数/通过率/硬门槛失败/稳定性）、四模块平均分、按 level/scenario/population 的通过率图、失败标签分布、评级分布、延迟，以及与上一次 run 的 diff。

#### Scenario: 查看单次评测看板

- **WHEN** 用户打开某次 run 的看板
- **THEN** 页面展示上述聚合指标与图表，数据来源于数据库

### Requirement: 用例结果列表与明细

前端 SHALL 提供用例结果列表（支持按 level、通过状态、稳定性、tag 筛选/排序），点击单条进入明细页，明细页 MUST 展示完整对话流水、各 judge verdict、扣分原因、命中关键词、per-run 稳定性与得分点。

#### Scenario: 从列表下钻到明细

- **WHEN** 用户在用例结果列表点击某条用例
- **THEN** 进入该用例明细页，展示其完整对话与判分细节

### Requirement: 跨 run 趋势看板

前端 SHALL 提供跨 run 趋势看板：按 benchmark 维度展示通过率与各模块平均分随版本（时间序列）的折线，以及失败标签趋势。

#### Scenario: 查看趋势

- **WHEN** 用户打开趋势看板并选择一个 benchmark
- **THEN** 页面展示该 benchmark 历次 run 的通过率/模块分折线与失败标签趋势
