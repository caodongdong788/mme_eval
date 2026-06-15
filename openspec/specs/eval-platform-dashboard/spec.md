# eval-platform-dashboard Specification

## Purpose
MME · Agent 评测平台的前端看板能力：benchmark 库浏览/上传、网页发起评测、评测列表与实时进度、单次评测看板（四模块/评级/失败标签/稳定性/性能）、用例明细下钻、与历史 run 的对比（通过率/回归/改善/判分指纹）以及跨 run 趋势可视化。
## Requirements
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

前端 SHALL 为单次 run 呈现聚合看板：核心指标卡（综合分/通过率/硬门槛失败/稳定性/待审）、四模块平均分、
分层级的用例数量与通过率（组合图）、失败标签分布（饼图）、延迟与成本（MUST 并排同一行展示），以及与上一次 run 的 diff。
看板内容 MUST 以「概览 / 用例明细」标签页组织；用例明细 MUST 含对话轮数列与轮数过滤。名称下方 meta MUST 精简为
judge 模型与 N（repeat 次数）两项。

#### Scenario: 查看单次评测看板

- **WHEN** 用户打开某次 run 的看板
- **THEN** 概览 MUST 展示上述聚合指标与图表，且延迟与成本 MUST 在同一行并排，用例明细 MUST 提供轮数列与轮数过滤

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

### Requirement: run 看板的重判 / 续跑 / 置顶操作

前端 run 看板 SHALL 提供「重判」「续跑」「置顶」操作入口：重判 / 续跑触发后端对应端点并在
成功后跳转到新产出的 run；置顶切换该 run 的保护状态并就地反映。当 run 不具备会话留痕
（`has_traces` 为假）时，重判 / 续跑入口 MUST 以禁用态或提示告知不可用，避免无效请求。

#### Scenario: 看板发起重判并跳转

- **WHEN** 用户在某成功 run 的看板点击「重判」
- **THEN** 前端调用重判端点，成功后跳转到新生成的 run 看板

#### Scenario: 不可重判时禁用入口

- **WHEN** 一个 run 的 `has_traces` 为假（无留痕，例如已被治理清理）
- **THEN** 看板的「重判 / 续跑」入口 MUST 不可用并给出原因提示

### Requirement: benchmark 列表展示上传人

Benchmark 库列表 SHALL 新增「上传人」列，展示 `created_by`（内置/无则展示占位）。

#### Scenario: 列表显示上传人

- **WHEN** 用户打开 Benchmark 库列表
- **THEN** 每行 MUST 显示该 benchmark 的上传人（或内置/未知占位）

### Requirement: 重判弹框可换 judge 模型

看板的「重判」入口 SHALL 提供一个弹框，允许用户在重判前：(a) 可选填新的 judge 模型
（provider/model/base_url/api_key）；(b) 可选从 benchmark 下拉中选一个 benchmark，提交后以其用例
判据 `cases_benchmark_id` 重判（默认不选＝沿用源 run 原判据）。提交后发起重判并跳转到新 run。
弹框 MUST 提示这些改动仅作用于本次重判、不改服务器配置，且 MUST NOT 提供四模块权重/阈值的编辑。

#### Scenario: 从弹框换模型发起重判

- **WHEN** 用户在重判弹框里填了新的 judge 模型并提交
- **THEN** 前端 MUST 携带该 judge 覆盖调用重判 API，并在新 run 创建后跳转到其看板

#### Scenario: 从弹框选 benchmark 重判

- **WHEN** 用户在重判弹框里选了一个 benchmark 并提交
- **THEN** 前端 MUST 携带 `cases_benchmark_id` 调用重判 API，按该集判据重判并跳转新 run

### Requirement: 看板按过滤子集在线编辑判据并另存新 benchmark

看板「用例结果」区 SHALL 提供「编辑判据(YAML)」入口，打开一个编辑器并以**当前过滤命中用例的
完整 YAML** 预填。用户编辑后可「另存为新 benchmark」：前端 MUST 调用 derive-yaml 派生一个新
benchmark（按 `sample_id` 只覆盖判据字段、未匹配丢弃），该操作 MUST NOT 触发重判、MUST NOT 修改
源 benchmark。重判改由重判弹框选该新 benchmark 单独发起。

#### Scenario: 在线编辑后另存新 benchmark

- **WHEN** 用户在「编辑判据(YAML)」里改了若干用例判据并点「另存为新 benchmark」
- **THEN** 前端 MUST 创建一个含改动的新 benchmark 且不触发重判，用户随后可在重判弹框选它重判

### Requirement: 看板审核队列与裁定界面

看板 SHALL 暴露人工审核能力：「用例结果」区 MUST 提供「待审 N」徽标与「仅看待审」筛选（数据取自
review-queue / review-stats），并 MUST 展示一张统计卡（人审通过率 / 分歧率 / 待审·已审计数）。
「仅看待审」筛选开启时 MUST 只展示在审核队列内且**尚未有人审结果**的用例（已裁定用例移出待审视图）。
「用例结果」区还 MUST 提供「人审结果」筛选（同意 / 推翻 / 未审），可与其它筛选叠加，并按 run 维度
随其它筛选条件一并记忆。
用例详情页 MUST 提供裁定面板：选择 `同意机器` / `推翻机器`、可填建议修正与备注并提交，提交后
MUST 展示该用例已有裁定列表。选「推翻机器」时面板 MUST 提供「去改判据(YAML)」入口，该入口 MUST
就地打开判据编辑器并仅预填当前用例 YAML（详见「用例明细就地编辑判据并单条试判预览」需求），MUST NOT
再跳转到看板列表页。看板统计 MUST NOT 改动 medeval 报告内核。

#### Scenario: 从详情页提交裁定

- **WHEN** 用户在用例详情页选择同意/推翻并提交
- **THEN** 前端 MUST 调用 annotate API 落库，并刷新展示该用例的裁定列表

#### Scenario: 看板呈现待审与统计

- **WHEN** 用户打开含待审用例的 run 看板
- **THEN** 看板 MUST 显示待审计数徽标，并可筛选只看待审用例，统计卡 MUST 显示人审通过率/分歧率

#### Scenario: 仅看待审排除已审用例

- **WHEN** 用户开启「仅看待审」且队列中部分用例已有人审结果
- **THEN** 列表 MUST 只显示队列内尚未裁定的用例，已裁定用例 MUST NOT 出现

#### Scenario: 按人审结果筛选

- **WHEN** 用户选择「人审结果=推翻」
- **THEN** 列表 MUST 只显示最新裁定为推翻的用例

#### Scenario: 推翻入口就地打开编辑器

- **WHEN** 用户在详情页选「推翻机器」并点「去改判据(YAML)」
- **THEN** 前端 MUST 就地打开判据编辑器（仅预填当前用例 YAML），MUST NOT 跳转到看板列表页

### Requirement: 看板必须展示成本/Token 卡片

run 看板 MUST 新增"成本 / Token（仅观测）"卡片，展示 `token_summary` 的总 token、平均每 run token，以及配置单价时的 cost。该卡片 MUST 明确为观测信息（不计分），与延迟卡片同等地位呈现。当本次 run 无 token 数据时，卡片 MUST 显示友好的"无 token 数据"提示而非空白或报错。

#### Scenario: 有 token 数据展示卡片

- **WHEN** 打开一个含 token 数据的 run 看板
- **THEN** MUST 显示总 token / 平均每 run token（配置单价时含 cost）

#### Scenario: 无数据友好提示

- **WHEN** run 无 token 数据
- **THEN** 卡片 MUST 显示"本次评测无 token 数据"提示

### Requirement: 看板筛选记忆与失败标签中文化

看板"用例结果"区的筛选条件（上线判定 / Level / 稳定性 / 仅看待审）MUST 在用户跳转到用例详情页
并返回后保持不变，按 run 维度记忆（同一会话内）。失败标签在看板用例列、标签分布图与用例详情的
judge 判定中 MUST 渲染中文短标签（来自 `GET /api/config/failure-tags`），未知值 MUST 回退原始值。

#### Scenario: 返回看板保留筛选

- **WHEN** 用户在看板设置了筛选条件，点开某用例详情后点「返回看板」
- **THEN** 看板 MUST 恢复此前的筛选条件并据此展示用例列表

#### Scenario: 失败标签显示中文

- **WHEN** 用例存在失败标签（如 `missed_red_flag`）
- **THEN** 看板与详情页 MUST 显示其中文短标签，而非英文枚举值

### Requirement: 用例结果表人审结果列

看板"用例结果"表 SHALL 新增「人审结果」列：对有人审裁定的用例渲染「同意」/「推翻」标签，
鼠标悬浮 MUST 展示该裁定的建议（suggestion）与备注（comment）；无裁定的用例 MUST 显示占位（如 -）。

#### Scenario: 列表展示人审结论并悬浮详情

- **WHEN** 某用例已被人工裁定为推翻并填写了建议
- **THEN** 该行「人审结果」列 MUST 显示「推翻」标签，悬浮 MUST 显示其建议与备注

### Requirement: 用例结果表列展示

看板"用例结果"表列标题 MUST 使用「场景描述」（用例链接列）与「类别」以避免语义混淆，且各列宽度
MUST 自适应内容（避免表头拥挤换行）。

#### Scenario: 列标题与自适应宽度

- **WHEN** 用户查看用例结果表
- **THEN** 链接列标题 MUST 为「场景描述」、分类列 MUST 为「类别」，且列宽 MUST 按内容自适应

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

### Requirement: 统一视觉设计体系

前端 MUST 采用一套统一的浅色设计体系（Langfuse/shadcn 风）：以临床青绿（`#0E6E5C`）为主色、近白底 +
细边框圆角卡片、等宽字体呈现 ID/指标/延迟/时间戳、软底淡色状态徽章。调色板与间距 MUST 通过 CSS 变量与
antd 主题 token 统一定义，SHALL NOT 在各页面散落硬编码色值。状态语义色 MUST 固定为：通过/同意=绿、
失败=红、待审/推翻=琥珀，且 MUST 使用低饱和软底；主色青绿仅用于激活/强调/关键数值与迷你趋势图。
本要求为纯前端呈现层规范，MUST NOT 改动后端契约、API 形状或判分内核。

#### Scenario: 跨页面视觉一致

- **WHEN** 用户在看板、评测列表、用例明细、Benchmark 库等页面间切换
- **THEN** 各页 MUST 共用同一套主色/字体/圆角/边框/徽章规范，呈现一致的浅色设计体系

#### Scenario: 状态徽章语义一致

- **WHEN** 页面展示通过/失败/待审或人审同意/推翻状态
- **THEN** MUST 使用约定的软底语义色（通过=绿/失败=红/待审/推翻=琥珀），不得使用主色青绿表达失败/告警

### Requirement: 应用骨架导航

前端应用骨架 MUST 提供浅色分组侧栏导航（按 评测 / 资源 / 系统 分组），侧栏 MUST 含顶部上下文位与底部
用户位，激活项 MUST 有明确视觉指示。单次 run 内容区 MUST 提供面包屑与标签页骨架以组织概览/明细/稳定性/
人工审核等视图入口。骨架改造 MUST 保留既有路由与页面功能不回归。

#### Scenario: 分组侧栏与激活指示

- **WHEN** 用户打开任一页面
- **THEN** 侧栏 MUST 以分组形式展示导航项，当前页对应项 MUST 呈激活态指示

#### Scenario: run 内容区面包屑/标签页

- **WHEN** 用户进入某次 run 的看板
- **THEN** 内容头 MUST 展示面包屑（评测 / run 名）与标签页骨架，且原有指标/图表/明细功能 MUST 保持可用

### Requirement: 看板评测在线改名

看板 MUST 支持对当前 run 评测名称的在线编辑：双击名称进入编辑态，失焦或回车时自动保存。保存 MUST 经后端
`PATCH /api/runs/{run_id}` 校验：空白名称 MUST 拒绝（422）；与其它 run 重名 MUST 拒绝（409 并提示）；run 不存在
MUST 返回 404；名称未变化（与自身相同）MUST 允许。改名只更新 `EvalRun.name`，MUST NOT 影响判分或产物。

#### Scenario: 双击改名并自动保存

- **WHEN** 用户双击看板评测名称、改为一个未被占用的新名并失焦
- **THEN** 前端 MUST 调用改名端点保存成功并就地更新标题

#### Scenario: 重名被拒

- **WHEN** 用户把名称改为与另一个已有 run 相同
- **THEN** 后端 MUST 返回 409，前端 MUST 提示重名且不更新标题

### Requirement: 用例明细对话轮数

用例明细 MUST 展示每条用例的对话轮数，并 MUST 提供按轮数过滤（单轮 / 多轮），该过滤可与其它筛选叠加并随筛选条件记忆。
后端 `GET /api/runs/{run_id}/cases` MUST 在每行返回 `n_turns`（由已落库 `detail_json` 推导，单轮=1、多轮>1），
并 MUST 支持 `turns=single|multi` 过滤参数。该能力 MUST NOT 新增数据库列或改判分内核。

#### Scenario: 展示并按轮数过滤

- **WHEN** 用户在用例明细选择「对话轮数=多轮」
- **THEN** 列表 MUST 只显示对话轮数大于 1 的用例，且每行 MUST 展示其轮数

### Requirement: 用例详情中文映射

用例详情页 MUST 对枚举/标识类值做中文映射展示：评分档（profile）、稳定性（stability）、维度分与扣分原因的维度
key（safety/compliance/function/experience）、Judge 列的 judge key（`hard_gate.*` / `rule.*` / `llm.*` / `scoring_point.*`）。
未知值 MUST 安全回退为原始字符串，且映射 MUST NOT 改变后端数据或判分。
此外，详情页返回操作 MUST 落到看板「用例明细」tab（而非「概览」），且看板 tab MUST 随选择记忆。

#### Scenario: 详情页中文呈现

- **WHEN** 用户打开某用例详情
- **THEN** 评分档/稳定性/维度 key/Judge key MUST 以中文呈现（未知值回退原文）

#### Scenario: 从详情返回用例列表

- **WHEN** 用户在用例详情页点击返回
- **THEN** MUST 回到该 run 看板的「用例明细」列表 tab

### Requirement: 判分模型配置中心

平台 MUST 提供「判分模型（LLM-as-Judge）配置」的全局 CRUD：后端 MUST 持久化 `judge_model_config`
（name 唯一、provider/model/base_url/api_version/temperature/api_key/created_by），并暴露
`GET/POST/PATCH/DELETE /api/judge-models`。配置 MUST 全局共享（所有登录用户可见可用）。
API Key MUST 落库但只写不读：读取类接口 MUST NOT 明文返回 Key，仅返回 `has_api_key` 掩码标记。
名称重复 MUST 返回 409。前端「资源」区 MUST 提供该配置页（增删改、Key 写入与掩码展示）。

#### Scenario: 配置后下拉复用且 Key 不外泄

- **WHEN** 用户在配置页保存一个带 API Key 的判分模型
- **THEN** 列表接口 MUST 只返回 `has_api_key=true` 而非明文 Key，且该模型 MUST 可在发起评测处被选用

### Requirement: 发起评测选择判分模型

发起评测 `POST /api/runs` MUST 支持 `judge_model_id`：选中时后端 MUST 据该配置构建 judge 覆盖
（连接信息 + 服务端读取的 Key 注入运行期），且 MUST NOT 把 Key 写入 run 的 `judge_overrides`；
未选时 MUST 沿用服务器 `config.yaml` 默认判分模型。发起评测页打分模型区 MUST 以下拉选择替代手填连接信息。

#### Scenario: 下拉选模型发起评测

- **WHEN** 用户在发起评测页选择某个已配置的判分模型并提交
- **THEN** 该 run MUST 用所选模型判分，且 run 的 `judge_overrides` MUST NOT 含明文 Key

### Requirement: 用例明细 Langfuse 链路入口

平台「用例明细」MUST 为每条用例提供「追踪链路」入口：当该用例存在 Langfuse trace 深链（`langfuse_trace_url`）时，前端 MUST 展示一个可点击入口，在新标签页打开该用例在自托管 Langfuse 的完整流程追踪；当深链为空（追踪关闭/未配置/旧 run）时，入口 MUST 隐藏。后端用例明细接口 MUST 暴露每条用例的 `langfuse_trace_url`（来自报告中代表 trace），且 MUST NOT 因该字段缺失而报错（旧 run 安全回退为空）。该入口 MUST NOT 改变任何判分数据或评分。

#### Scenario: 有链路时可一键跳转

- **WHEN** 某条用例的报告含非空 `langfuse_trace_url`
- **THEN** 用例明细 MUST 展示「追踪链路」入口，点击 MUST 在新标签页打开该 trace

#### Scenario: 无链路时隐藏入口

- **WHEN** 某条用例无 `langfuse_trace_url`（追踪关闭/未配置/旧 run）
- **THEN** 用例明细 MUST NOT 展示该入口，且页面 MUST 正常渲染

### Requirement: 看板进入默认概览与对话流水可滚动

从评测列表进入某个 run 看板时，平台 MUST 默认显示「概览」tab；仅当用户从「用例明细」打开的用例详情页点击「返回」时，MUST 落回「用例明细」tab。看板 tab 状态 MUST NOT 跨「从列表进入」复用上一次停留的 tab（即不得因 tab 记忆导致进入即停在非概览页）。用例筛选条件的记忆 MUST NOT 受影响。

用例详情页的「对话流水」MUST 限定一个固定高度，内容超出时 MUST 可上下滚动查看，且 MUST NOT 撑高整页布局。

#### Scenario: 从列表进入默认概览

- **WHEN** 用户在评测列表点击某个 run 的看板或名称
- **THEN** 看板 MUST 显示「概览」tab，而非上次停留的 tab

#### Scenario: 从用例详情返回落用例明细

- **WHEN** 用户从「用例明细」打开某用例详情后点击「返回」
- **THEN** 看板 MUST 落回「用例明细」tab

#### Scenario: 长对话可滚动

- **WHEN** 某用例对话流水很长、超出固定高度
- **THEN** 对话流水区 MUST 可上下滚动查看，整页布局 MUST NOT 被撑高

### Requirement: 用户登录信息置于右上角

平台 MUST 在页面右上角（顶部 header）展示当前登录用户信息与退出入口，MUST NOT 仍置于左侧导航栏底部。未登录时 MUST 不展示该入口。

#### Scenario: 右上角展示用户

- **WHEN** 用户已登录并进入平台任意页面
- **THEN** 右上角 MUST 展示用户名/头像与退出登录入口

### Requirement: 判据 YAML 覆盖保存原 benchmark

用例明细的「编辑判据(YAML)」除「另存为新 benchmark」外，MUST 支持「覆盖当前 benchmark」：覆盖的合并语义 MUST 与另存完全一致（复制源集全部用例、按 `sample_id` 只合并判据字段、未匹配 `sample_id` 丢弃、零匹配报错、源集中不在本次编辑的用例原样保留），区别仅在于写回原 benchmark 而非新建。内置 benchmark MUST 禁止覆盖（后端拒绝、前端禁用入口）。覆盖 MUST NOT 影响任何历史 run 的冻结用例与判分结果。

#### Scenario: 覆盖更新原集判据

- **WHEN** 用户在用例明细编辑判据后选择「覆盖当前 benchmark」
- **THEN** 原 benchmark 中匹配 `sample_id` 的用例判据字段 MUST 被更新，未编辑的用例 MUST 原样保留，且 MUST 不新建 benchmark

#### Scenario: 内置集禁止覆盖

- **WHEN** 当前 benchmark 为内置（`source=builtin`）
- **THEN** 覆盖入口 MUST 不可用，后端 MUST 拒绝覆盖请求

### Requirement: 重判换 judge 模型从判分模型库下拉选

重判弹框更换 LLM judge 模型 MUST 改为从「判分模型库」下拉选择已保存配置（连接信息与 Key 由服务端注入、不入库），MUST NOT 再要求用户手填 provider/model/base_url/api_key。选中不存在的判分模型 MUST 返回 404。

#### Scenario: 下拉选判分模型重判

- **WHEN** 用户在重判弹框下拉选择某个已保存判分模型
- **THEN** 重判 MUST 使用该模型的连接信息与 Key 重跑判分，且入库覆盖记录 MUST NOT 含明文 api_key

### Requirement: 仅重判上线失败用例并合并重算

重判 MUST 支持可选项「只重判上线判定失败（`release_passed=false`）的用例」，默认仍为全量重判。启用时，系统 MUST 只对失败用例重放冻结留痕重判，通过用例 MUST 沿用源 run 的判分结果，合并后 MUST 重算整体分数、通过率与分布。重判 MUST 仍产出新 run（`parent_run_id` 指向源、源 run 不可变、默认与源 diff），且 MUST NOT 触发任何 bot 调用。源 run 无失败用例时该模式 MUST 返回 400。

#### Scenario: 只重判失败用例

- **WHEN** 用户勾选「只重判上线失败」并发起重判
- **THEN** 新 run 中失败用例 MUST 用新判据/模型重判出新结果，通过用例 MUST 沿用源结果，整体通过率/分数 MUST 据合并结果重算

#### Scenario: 无失败用例时拒绝

- **WHEN** 源 run 没有 `release_passed=false` 的用例却勾选「只重判上线失败」
- **THEN** 系统 MUST 返回 400 并提示无失败用例可重判

### Requirement: 用例详情维度分展示满分

用例详情的「维度分」MUST 以 `当前分/满分` 格式展示每个维度（安全/合规/功能/体验），满分取该题所属评分 profile 的 `module_max`。当结果来自不含满分信息的历史 run 时，MUST 优雅回退为仅展示当前分值，不报错。

#### Scenario: 展示维度满分

- **WHEN** 打开一条用例详情且其结果含维度满分信息
- **THEN** 每个维度 MUST 显示为 `分/满分`（如对抗档 `体验 0.075/0.10`）

### Requirement: 上线综合分阈值前端按场景可配

平台 MUST 提供前端入口，按评分档（profile：default/red_flag/adversarial/knowledge/rehab）分别配置「综合分上线阈值」。配置 MUST 持久化，且 MUST 作用于之后发起的**新评测与重判**——注入该 run 的 `config_snapshot` 并进入判分 `fingerprint`，使 diff 可区分口径变化。重判仍冻结 bot 会话留痕（零 bot 调用），仅判分口径随当前阈值配置变化。未配置的 profile MUST 完全沿用服务端 `config.yaml` 现状（零行为变化）。阈值覆盖 MUST 只改综合分阈值，MUST NOT 削弱该 profile 原有的安全/合规 gates 与 HardGate。阈值越界（≤0 或 > 该 profile 满分）或未知 profile MUST 返回 422。

#### Scenario: 按场景调上线阈值并对新评测生效

- **WHEN** 用户把某评分档的综合分上线阈值改为某合法值并保存，随后发起新评测
- **THEN** 新评测对该档用例的 `release_passed` MUST 按新阈值判定，且该阈值 MUST 写入新 run 的 `config_snapshot`

#### Scenario: 调上线阈值后重判历史 run 生效

- **WHEN** 用户把某评分档阈值改为更严格的值并保存，随后对一历史 run 发起重判
- **THEN** 重判产出的新 run 对该档用例的 `release_passed` MUST 按新阈值判定（原 0.80 通过的知识档用例在阈值升到 0.90 后 MUST 失败），且新阈值 MUST 写入新 run 的 `config_snapshot`

#### Scenario: 未配置时不改变现状

- **WHEN** 未对某 profile 设置任何阈值覆盖
- **THEN** 该 profile 在新评测与重判中的上线判定 MUST 与 `config.yaml` 原 `pass_rule` 逐字节一致

#### Scenario: 非法阈值拒绝

- **WHEN** 提交的阈值 ≤0、超过该 profile 满分，或 profile 未知
- **THEN** 系统 MUST 返回 422 且不落库

### Requirement: 得分点惩罚项清晰展示

用例详情「得分点」表 MUST 区分正分点与惩罚（负分）得分点。惩罚点 MUST NOT 显示无意义的 `0/0`：未触发时显示「未触发·罚则 -N」，已触发（出现被惩罚内容）时显示「已扣 -N」。说明 MUST 带出该点的符号与判据，使扣分性质一目了然。

#### Scenario: 惩罚点未触发

- **WHEN** 某负分得分点未触发（bot 未出现被惩罚内容）
- **THEN** 该行 MUST 显示为「未触发·罚则 -N」而非 `0/0`

### Requirement: 用例详情展示指南匹配率

用例详情 MUST 展示「指南匹配率」，以 `X%（matched/total）` 形式给出，其中 matched/total 为带指南锚点得分点的命中数与总数。当用例无带指南锚点的得分点时，MUST 显示「无指南锚点」而非 0%。

#### Scenario: 有指南锚点

- **WHEN** 用例存在带指南锚点的得分点且全部命中
- **THEN** 指南匹配率 MUST 显示为 `100%（n/n）`

### Requirement: 用例列表按指南匹配率过滤

用例列表 MUST 支持按指南匹配率过滤，至少提供「100%」「<100%」「无指南锚点」三档，服务端 MUST 按 `guideline_match_rate` 过滤（100%=匹配率为 1.0；<100%=非空且小于 1.0；无指南锚点=匹配率为空）。

#### Scenario: 过滤未满分

- **WHEN** 用户选择「<100%」过滤
- **THEN** 列表 MUST 只返回 `guideline_match_rate` 非空且小于 1.0 的用例

### Requirement: 用例列表指南匹配率带命中计数

用例列表的「指南匹配率」列 MUST 在百分比之外带出具体命中计数，以 `X%（matched/total）` 形式展示，其中 matched/total 为该用例带指南锚点得分点的命中数与总数。计数 MUST 由服务端从已落 `detail_json` 派生（`CaseRowOut.guideline_matched` / `guideline_total`），无需数据库迁移、对历史 run 同样生效。当用例无带指南锚点的得分点时，列 MUST 显示「无锚点」而非 `0/0`。

#### Scenario: 列表带计数

- **WHEN** 某用例有 6 个带指南锚点的得分点且全部命中
- **THEN** 列表该行指南匹配率 MUST 显示为 `100%（6/6）`

#### Scenario: 无指南锚点

- **WHEN** 某用例无带指南锚点的得分点
- **THEN** 列表该行 MUST 显示「无锚点」而非 `0/0` 或 `0%`

### Requirement: 用例明细就地编辑判据并单条试判预览

用例明细页 SHALL 支持就地（不跳离当前页）编辑当前用例判据并预览重判效果。HITL 裁定面板选「推翻机器」
时，「去改判据(YAML)」入口 MUST 就地打开判据编辑器（复用看板同一编辑器组件），并 MUST 以**仅当前
`sample_id` 这一条用例**的完整 YAML 预填（前端经带 `sample_id` 的 cases-yaml 取得）。

编辑器内 MUST 提供醒目的「试判此用例（预览）」动作：前端 MUST 调用 preview-rejudge 端点，展示新
verdict / 四维分 / 综合分 / 上线判定、与当前值的 diff，以及**本次扣分项**（`score_deductions`）。该预览
MUST 明确标注为「仅预览，不修改当前 run」，且 MUST NOT 触发任何落库或重判。用户满意后 MUST 可经
「覆盖当前 benchmark」把判据落回这次评测当前关联的 benchmark（用例明细入口为**仅覆盖**模式，
MUST NOT 提供「另存为新 benchmark」与新名称输入）；界面 MUST 提示「覆盖仅更新判据源、不改当前 run
已存分，要得到修正结果需另行重判」。编辑器标题 MUST 形如「改判据 · <用例描述>」，MUST NOT 堆叠冗长后缀。

#### Scenario: 推翻后就地编辑单条判据

- **WHEN** 用户在用例明细 HITL 面板选「推翻机器」并点「去改判据(YAML)」
- **THEN** 前端 MUST 就地打开判据编辑器并仅预填当前用例 YAML，MUST NOT 跳转到看板列表页

#### Scenario: 单条试判预览不改当前 run

- **WHEN** 用户在编辑器内修改判据后点「试判此用例（预览）」
- **THEN** 前端 MUST 调用 preview-rejudge 并展示新判定、diff 与本次扣分项，且 MUST 标注「仅预览、不改当前 run」，
  MUST NOT 触发落库或重判

#### Scenario: 用例明细编辑器仅覆盖

- **WHEN** 用户从用例明细页打开判据编辑器
- **THEN** 编辑器 MUST 仅提供「覆盖当前 benchmark」，MUST NOT 显示「另存为新 benchmark」与新 benchmark 名称输入

### Requirement: 判据编辑器展示当前 benchmark 名称

判据编辑器（看板入口与用例明细入口共用）MUST 在界面显著位置展示**当前正在编辑/覆盖的 benchmark 名称**
（形如 `#<id>「<名称>」`），使用户在「覆盖当前 benchmark」前能确认覆盖对象，避免误覆盖。

#### Scenario: 编辑判据时可见 benchmark 名称

- **WHEN** 用户打开判据编辑器
- **THEN** 编辑器 MUST 展示当前 run 关联 benchmark 的 `#id「名称」`

### Requirement: Pairwise 对比入口

看板 SHALL 提供「Pairwise 对比」入口，允许用户选择两次评测（A 基线 / B 本次）与一个
裁判模型并发起对比。当所选两个 run 不可比（判分尺子不同/benchmark 不同/用例集合不
一致/缺 trace）时，界面 MUST 给出中文错误提示而非静默失败。

#### Scenario: 选择两次 run 发起对比
- **WHEN** 用户在入口选定两个可比的 run 与裁判模型并提交
- **THEN** 界面创建一次比较并跳转到结果页（展示进行中状态）

#### Scenario: 不可比时报错
- **WHEN** 用户选择判分尺子不同的两个 run
- **THEN** 界面 MUST 展示「判分尺子不同不可比」的中文提示

### Requirement: Pairwise 结果展示

结果页 SHALL 含三块：①整体总结（哪次质量更高、胜/平/负、按维度胜率、回退用例清单、
被测差异 `subject_diff`）；②逐用例对比列表（可按 `winner` 筛选/排序）；③单题详情——
A/B 完整对话左右并排、该题判定理由与各维度归属。回退用例（B 更差）MUST 可被显著标识
以便人工复核。

#### Scenario: 查看整体总结
- **WHEN** 比较完成
- **THEN** 顶部展示整体结论与按安全/功能/体验维度的胜率，并列出回退用例

#### Scenario: 下钻单题对比
- **WHEN** 用户点击列表中某用例
- **THEN** 展示 A/B 完整对话左右并排与该题判定理由

### Requirement: 看板视觉设计契约（Ink & Whitespace）

前端看板 SHALL 遵循 `DESIGN.md` 的「The Clinical Instrument — Ink & Whitespace」视觉契约，并以
`frontend/src/styles.css` 的 `:root` 变量与 `frontend/src/theme.ts` 的 `palette` 为**镜像一致的
单一信任源**。具体约束：

- 底面 MUST 为纯白 `#FFFFFF`；卡片 / KPI / 区块 MUST NOT 带可见边框或卡片阴影，模块区隔
  MUST 仅依靠留白（浮层 Modal/Dropdown/登录卡的柔和阴影、表格行底 1px 发丝线除外）。
- 顶部核心指标 MUST 用系统无衬线大字号（≈40px）+ 近黑 `#111827`；辅助文字 MUST 用
  小字号浅灰 `#9CA3AF`。
- 状态指示 MUST 用 6px 纯色圆点 + 深灰文字，MUST NOT 用面状彩色 Tag/Badge；状态 MUST 始终保留
  文字标签（不只靠颜色，兼顾色觉无障碍）。
- 数据表格 MUST 去竖网格线 / 去斑马纹 / 去表头底色，仅保留 1px 发丝水平行线并加大单元内边距。
- 图表 MUST 关闭背景网格线、隐藏轴线 / 刻度线（仅留浅灰轴文字）、调细线柱，配色 MUST 为冷灰阶 +
  单一墨黑强调序列（主强调 `#111827`、次级序列 `#6B7280`）。
- 墨黑 ink `#111827` MUST 为唯一交互强调色（链接 / 主按钮 / 选中 / 聚焦 / 图表强调）；MUST NOT 引入
  任何品牌彩色强调（含 teal）。主按钮 MUST 为墨黑实底 + 白字、hover 提亮为深灰 `#374151`；链接
  MUST 为墨黑并在 hover 加下划线以保留可点可感。功能性语义圆点 pass/warn/fail 不属品牌强调、不受此约束。
  表内 ID / 分数 / 数字列 MUST 用 JetBrains Mono + `tnum` 保对齐。

#### Scenario: 单次评测看板呈现核心指标与状态

- **WHEN** 用户打开某次成功 run 的看板
- **THEN** 顶部综合分 / 通过率以 ≈40px 近黑系统无衬线大字呈现、副信息为浅灰小字
- **AND** 用例表无竖网格线 / 无斑马纹 / 无表头底色、仅水平发丝行线
- **AND** 「上线判定 / 稳定性 / 运行状态」等以 6px 圆点 + 深灰文字呈现，绝不只靠红绿色块

#### Scenario: 图表降噪渲染

- **WHEN** 看板渲染分层级 / 四模块 / 趋势等图表
- **THEN** 图表 MUST NOT 显示背景网格线与坐标轴实线 / 刻度线，仅保留浅灰轴文字
- **AND** 线 / 柱为细描边、冷灰阶 + 单一墨黑强调，无大面积高饱和色块

#### Scenario: 交互强调为墨黑单色（无品牌彩色）

- **WHEN** 用户查看主按钮 / 链接 / 选中态 / 图表强调序列
- **THEN** 它们 MUST 为墨黑 `#111827`（主按钮实底白字、hover 深灰 `#374151`）
- **AND** 全站 MUST NOT 出现 teal 或任何其它品牌彩色强调（功能性 pass/warn/fail 圆点除外）

### Requirement: 取数失败的错误兜底状态

看板各页面在调用后端接口失败时 SHALL 渲染明确的错误兜底状态（如错误提示与重试入口），MUST NOT 因为请求失败而停留在永久加载（无限 loading）状态。详情类页面（run 详情、用例详情、pairwise 详情）在目标资源不存在或加载失败时 MUST 给出可读的失败提示而非空白或常驻 Spin。

#### Scenario: 详情接口失败不再无限 loading

- **WHEN** 打开某 run/用例详情页且其数据接口返回错误
- **THEN** 页面 MUST 展示错误提示与重试/返回入口，而非持续显示加载占位

#### Scenario: 应用级未捕获错误不白屏

- **WHEN** 某页面渲染抛出未捕获异常
- **THEN** 应用 MUST 由错误边界兜底展示降级界面，而非整页白屏

### Requirement: 前端页面组件化与快照测试

前端 `pages/` 层 SHALL 仅承担路由参数、数据获取与页面级 state 编排；可复用的展示与交互块
MUST 沉淀至 `frontend/src/components/`（或 `utils/` 纯函数），禁止在单页文件内堆积数百行 UI。
从 `RunDashboardPage` / `CaseDetailPage` 抽出的核心块（含 `ConversationThread`、`FilterToolbar` 及
关联判定/复核卡片）MUST 配套 vitest + `@testing-library/react` 快照或单元测试，以锁定拆分前后
UI 结构与关键文案一致；纯重构 MUST NOT 改变筛选、对话展示、路由回退或 sessionStorage 筛选项记忆等行为。

#### Scenario: 看板与用例明细由子组件组装且行为不变

- **WHEN** 用户打开 run 看板的用例明细 Tab 或用例详情页
- **THEN** 筛选工具栏、对话流水、Judge 判定表等 MUST 由独立 components 渲染
- **AND** 筛选、下钻、返回、人工复核等交互 MUST 与拆分前一致

#### Scenario: 抽出组件具备快照回归

- **WHEN** 维护者修改 `ConversationThread` 或 `FilterToolbar` 等已抽出组件
- **THEN** `npm run test` MUST 能通过对应 snapshot / 单元测试，否则视为非预期 UI 漂移

