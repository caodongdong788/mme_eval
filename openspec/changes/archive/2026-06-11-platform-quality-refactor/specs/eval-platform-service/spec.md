## ADDED Requirements

### Requirement: 产物路径边界安全

系统 SHALL 保证所有由 `run_name`/slug/benchmark 标识拼接出的文件系统路径都限制在受控根目录（`outputs/`、`uploads/`）之内。`run_slug` 生成 MUST 对名称做字符白名单消毒，去除路径分隔符与 `..` 等穿越片段；任何读/写/删除产物前 MUST 经统一 `safe_join` 校验目标路径 `is_relative_to` 受控根，越界 MUST 拒绝（HTTP 400）。本需求 MUST NOT 改变既有合法 slug 的产出结果。

#### Scenario: 含穿越片段的 run 名称被消毒

- **WHEN** 以包含 `../` 或路径分隔符的 `run_name` 发起评测或解析其产物目录
- **THEN** 系统 MUST 生成限制在 `outputs/` 内的安全 slug，且对应产物路径 MUST 落在 `outputs/` 根之内

#### Scenario: 越界产物路径被拒绝

- **WHEN** 任意端点尝试访问解析后落在受控根之外的产物路径
- **THEN** 系统 MUST 拒绝该操作并返回错误，而非读写根目录之外的文件

### Requirement: benchmark 上传大小上限

系统上传 benchmark YAML 的端点 SHALL 限制请求体大小，超过上限 MUST 拒绝并返回可读错误（HTTP 413/400），以避免超大上传导致内存耗尽。上限 MUST 可经配置调整。

#### Scenario: 超限上传被拒绝

- **WHEN** 用户上传超过配置上限的文件
- **THEN** 系统 MUST 拒绝保存并返回大小超限的错误信息，不读入全部内容

### Requirement: 生产环境会话密钥强校验

当运行于生产环境时，系统 SHALL 拒绝使用默认/不安全的 `SESSION_SECRET` 启动：若检测到生产环境且密钥仍为内置默认值，启动 MUST 失败并给出明确错误。HTTPS 部署下会话 cookie SHALL 标记 `Secure`。开发/测试环境 MUST 保持现有默认值可直接启动。

#### Scenario: 生产使用默认密钥启动失败

- **WHEN** 在生产环境标识下以默认 `SESSION_SECRET` 启动服务
- **THEN** 启动 MUST 失败并提示需配置安全密钥

#### Scenario: 开发环境默认密钥可用

- **WHEN** 在开发/测试环境以默认配置启动
- **THEN** 服务 MUST 正常启动，行为与现状一致

### Requirement: 运行列表分页

`GET /api/runs` SHALL 支持可选分页参数（`limit`/`offset`）。未提供分页参数时，行为 MUST 与现状兼容（返回按现有排序的列表，受一个安全的默认上限约束）。

#### Scenario: 默认请求保持兼容

- **WHEN** 不带分页参数请求运行列表
- **THEN** 系统返回与现状一致的列表（受默认上限约束），现有前端无需改动即可工作

#### Scenario: 带分页参数请求

- **WHEN** 带 `limit`/`offset` 请求运行列表
- **THEN** 系统返回对应分页切片

### Requirement: 全局异常处理与优雅关闭

系统 SHALL 注册全局异常处理器，将未捕获异常与请求校验错误统一为结构化错误响应（生产环境 MUST NOT 泄漏堆栈细节）。应用 `lifespan` SHALL 在关闭阶段优雅收尾后台任务（评测/对比任务），避免进程退出时丢失或半写状态。

#### Scenario: 未捕获异常返回统一错误体

- **WHEN** 某请求处理过程中抛出未预期异常
- **THEN** 系统 MUST 返回统一格式错误响应，生产环境不暴露内部堆栈

#### Scenario: 关闭时收尾后台任务

- **WHEN** 服务收到关闭信号且存在进行中的后台任务
- **THEN** `lifespan` shutdown MUST 尝试取消/等待这些任务收尾
