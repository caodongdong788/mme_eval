# eval-platform-dashboard Specification (delta)

## ADDED Requirements

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
