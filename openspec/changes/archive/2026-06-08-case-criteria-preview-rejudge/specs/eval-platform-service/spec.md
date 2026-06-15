## ADDED Requirements

### Requirement: 单用例 ephemeral 试判预览

系统 SHALL 提供 `POST /api/runs/{run_id}/cases/{sample_id}/preview-rejudge`：接收针对该 `sample_id`
的判据覆盖（结构化 `CaseLogicOverride`，或等价的单条用例 `yaml_text`，服务端按 sample_id 抽取
`expected_behavior` / `hard_gates` / `rubric` / `scoring_points` 四块），用该 run 中该用例的**冻结
会话留痕**与套用覆盖后的判据，仅重跑判分并重算评分，返回新 verdict 列表、四维分、综合分、上线判定，
以及与该用例当前已存结果的 diff。`yaml_text` 中找不到该 `sample_id` 时 MUST 返回 400。

该端点 MUST 为只读旁路：MUST NOT 写任何库、MUST NOT 新建 run 或产物目录、MUST NOT 复制留痕、
MUST NOT 修改当前 run 的判分、MUST NOT 写入 `case_annotation`。判据合并 MUST 复用与 benchmark 派生
一致的 `sample_id` 覆盖语义；判分 MUST 经与正式重判同一路径（`judge_traces` + 评分），且 MUST NOT
调用被测 bot。

该用例无冻结留痕可用（如 `n_runs>1` 且留痕已被存储治理清理而无法重建代表 trace）时，系统 MUST 返回
400 及可读原因；run 或 `sample_id` 不存在 MUST 返回 404。

#### Scenario: 试判返回新判定且零落库

- **WHEN** 用户对某 run 某用例带编辑后的判据请求 preview-rejudge
- **THEN** 系统 MUST 仅以该用例冻结留痕重跑判分、返回新 verdict / 四维分 / 上线判定及与当前值的 diff，
  且 MUST NOT 写库、MUST NOT 新建 run、MUST NOT 调用被测 bot、MUST NOT 改动当前 run 的判分

#### Scenario: 留痕缺失无法试判

- **WHEN** 目标用例的冻结留痕已被清理且无法重建代表 trace
- **THEN** 系统 MUST 返回 400 并提示无可用留痕、无法试判

#### Scenario: 用例不存在

- **WHEN** 请求的 `sample_id` 不在该 run 的结果中
- **THEN** 系统 MUST 返回 404

## MODIFIED Requirements

### Requirement: 导出过滤用例的完整 YAML 供在线编辑

系统 SHALL 提供 `GET /api/runs/{run_id}/cases-yaml`，接收与 `GET /api/runs/{run_id}/cases`
相同的过滤参数（level / release_passed / stability / scenario / tag），并 SHALL 额外支持可选的
`sample_id` 过滤参数以**只导出单条指定用例**的 YAML（供用例明细页就地编辑）。系统返回该 run 命中用例在其
benchmark 中的**完整用例 YAML 文本**（可被 `load_cases` 解析），供前端预填判据编辑器。run 无关联
benchmark、过滤后无用例、或指定的 `sample_id` 不在命中集时 MUST 返回 400。

#### Scenario: 按过滤导出可解析 YAML

- **WHEN** 用户带过滤参数请求某 run 的 cases-yaml
- **THEN** 返回的 YAML MUST 仅含命中用例的完整定义，且可被 `load_cases` 解析校验

#### Scenario: 按 sample_id 导出单条用例 YAML

- **WHEN** 用户带 `sample_id` 参数请求某 run 的 cases-yaml
- **THEN** 返回的 YAML MUST 仅含该单条用例的完整定义，可被 `load_cases` 解析校验
