# eval-platform-dashboard Specification (delta)

## ADDED Requirements

### Requirement: Benchmark 库模板入口与编辑

Benchmark 库列表 MUST 只展示上传/派生的 benchmark，内置 benchmark MUST NOT 出现在列表中。
内置 benchmark MUST 以「用例模板」入口呈现于"上传 benchmark"按钮左侧，点击 MUST 可查看其用例清单。
列表中每条上传 benchmark MUST 提供"编辑"操作，打开弹窗修改名称与描述并保存（调用 PATCH 接口）。

#### Scenario: 内置作为模板入口

- **WHEN** 用户打开 Benchmark 库
- **THEN** 列表 MUST 不含内置项，且页首"上传"按钮左侧 MUST 有「用例模板」入口可查看内置用例

#### Scenario: 编辑名称与描述

- **WHEN** 用户点击某上传 benchmark 的"编辑"，修改名称/描述并保存
- **THEN** 前端 MUST 调用 PATCH 接口并刷新列表显示新值
