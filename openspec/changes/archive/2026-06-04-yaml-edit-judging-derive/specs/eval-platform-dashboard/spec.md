# eval-platform-dashboard Specification (delta)

## REMOVED Requirements

### Requirement: 用例详情页可编辑判据并另存重判

**Reason**: 逐条结构化编辑且每改一条即自动派生 + 立即重判，耦合过重、不可批量。改为看板按过滤
子集做 YAML 在线编辑、另存与重判解耦（见下方新需求）。

## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: 看板按过滤子集在线编辑判据并另存新 benchmark

看板「用例结果」区 SHALL 提供「编辑判据(YAML)」入口，打开一个编辑器并以**当前过滤命中用例的
完整 YAML** 预填。用户编辑后可「另存为新 benchmark」：前端 MUST 调用 derive-yaml 派生一个新
benchmark（按 `sample_id` 只覆盖判据字段、未匹配丢弃），该操作 MUST NOT 触发重判、MUST NOT 修改
源 benchmark。重判改由重判弹框选该新 benchmark 单独发起。

#### Scenario: 在线编辑后另存新 benchmark

- **WHEN** 用户在「编辑判据(YAML)」里改了若干用例判据并点「另存为新 benchmark」
- **THEN** 前端 MUST 创建一个含改动的新 benchmark 且不触发重判，用户随后可在重判弹框选它重判
