## REMOVED Requirements

### Requirement: 系统必须输出 HTML 报告以提供本地完整视图

**Reason**: HTML 输出与 Markdown 信息重复（评审者实际不打开 HTML，只看飞书文档与本地 .md），但维护一份 Jinja2 模板与额外的样式约束会拖慢迭代。删除 HTML 让"产物只剩用户真正看的那一份"，也让"报告样式有歧义"这件事消失（统一以 markdown 为准）。

**Migration**: 现存 `outputs/*/report.html` 文件保留不动；新跑不再生成。CI workflow 中如有上传 `report.html` 的步骤须改为上传 `report.md`。

## MODIFIED Requirements

### Requirement: 系统必须输出 JSON 报告作为版本对比的可信数据源

`write_json(report, path)` MUST 把整个 `RunReport`（包含每条 CaseResult 的完整 case、trace、verdicts 字段）以 UTF-8 写到磁盘，缩进 2 空格。JSON MUST 是 diff 的唯一信任源——HTML 已废弃、Markdown 都可以丢，JSON 不能丢。

**新增约束**：`report.json` MUST 在每次 `medeval run` 完成时无条件写盘，不再受 `reporter.formats` 配置控制。`reporter.formats` 列表的语义重新定义为"用户面可读产物"，JSON 不属于该列表。即使用户配置 `formats: []` 或不写该字段，`report.json` 仍然 MUST 落盘。

#### 场景: JSON 必须完整保留每条 verdict 的 evidence

- **当** 写入一份含 1 条 fail 用例的 RunReport
- **那么** JSON 中该用例对应的 verdict 必须包含 `evidence` 数组、`reason`、`failure_tags`，便于人审复盘

#### 场景: report.json 必须无条件写盘

- **当** `reporter.formats` 配置为 `[]` 或缺失，且 `medeval run` 成功完成
- **那么** `outputs/<run>/report.json` 必须存在并可被 `diff_runs` 读取；不得因 `formats` 列表为空而省略

### Requirement: 系统必须支持把 Markdown 报告自动发布到飞书

`publish_to_lark(markdown_content, parent_folder_token)` MUST 调用本机已登录的 `lark-cli docs +create --api-version v2 --doc-format markdown`，成功时返回 `data.document.url`，失败时返回 None 并仅记录日志（MUST 不抛异常打断主流程）。命令 MUST 以 argv 列表传参避免 shell 转义问题，并对超过 200KB 的 Markdown 做截断处理。

**新增约束**：`reporter.lark.enabled` 默认值 MUST 为 `true`（即每次 `medeval run` 默认尝试发布到飞书）。用户若需关闭须显式 `reporter.lark.enabled: false`。当 lark-cli 未安装或登录失效时仍按原规则降级（返回 None、记录 warning，不阻断主流程）。

#### 场景: lark-cli 未安装

- **当** PATH 中找不到 `lark-cli`
- **那么** `publish_to_lark` 必须返回 None，并在日志中给出明确警告，禁止 raise

#### 场景: lark-cli 退出码非 0

- **当** `lark-cli` 返回 stderr 含权限错误
- **那么** `publish_to_lark` 必须返回 None，stderr 必须被记录到 ERROR 级日志

#### 场景: Markdown 过大时必须截断

- **当** 输入 Markdown 超过 200KB
- **那么** `publish_to_lark` 必须截断到约一半长度并追加"_（内容过长已截断，完整报告见 JSON 输出）_"提示，仍然继续发布

#### 场景: 默认开启飞书发布

- **当** 用户的 config.yaml 中未显式配置 `reporter.lark.enabled`
- **那么** `medeval run` 完成后 MUST 自动尝试发布飞书文档；终端必须打印"飞书文档已发布：<url>"或失败警告

#### 场景: 显式关闭飞书发布

- **当** 用户配置 `reporter.lark.enabled: false`
- **那么** `medeval run` MUST 不调用 `publish_to_lark`，且不打印飞书相关 log

## ADDED Requirements

### Requirement: reporter.formats 必须只接受 ["markdown"] 一个有效值（HTML 废弃后）

`reporter.formats` 配置字段在本 change 后只接受 `["markdown"]`、`[]` 或缺省（默认 `["markdown"]`）。如果用户配置含 `"html"`，CLI MUST 在加载 config 时给出明确报错：`reporter.formats no longer supports "html" (removed in change trim-report-formats); please remove this entry from your config`。

如果用户配置含 `"json"`，CLI MUST 给出 warning 但不报错：`reporter.formats no longer needs "json" (always written); ignoring`。

#### 场景: 历史 config 含 html

- **当** 用户用旧 config.yaml `formats: ["html","markdown","json"]` 跑新版 CLI
- **那么** CLI MUST 立即报错并退出非 0；错误消息引导用户修改 config

#### 场景: 配置为空列表

- **当** 用户配置 `reporter.formats: []`
- **那么** Markdown / HTML 都不生成；但 `report.json` 仍然写盘（基础设施不受 formats 控制）；不报错
