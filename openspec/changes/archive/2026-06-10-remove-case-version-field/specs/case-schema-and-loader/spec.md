## MODIFIED Requirements

### Requirement: 系统必须以 Pydantic 模型定义所有用例字段

系统 MUST 为每一条 YAML 用例提供严格的 Pydantic v2 Schema，覆盖 sample_id、scenario / sub_scenario、level（L1/L2/L3/L4）、population（adult/child/pregnant/elderly/chronic/mental/general）、difficulty（easy/medium/hard）、tags、source、turns、expected_behavior、hard_gates、rubric、failure_tags_candidates、notes 等字段。所有枚举字段必须使用 Enum 限定取值范围，禁止接受未声明的取值。Schema MUST NOT 再声明 `case_version` 字段；历史 YAML 中残留的 `case_version` key MUST 被静默忽略而非抛错（`extra` 默认 ignore）。

#### 场景:加载合法 YAML 用例

- **当** 用户调用 `load_cases(include=["cases"], base_dir=ROOT)` 加载一个符合 schema 的 YAML 文件
- **那么** 系统必须为每条记录返回一个 `TestCase` 实例，level/population/difficulty 等字段被解析为对应的 Enum 值，`hard_gates` / `expected_behavior` / `rubric` 即使用例未声明也必须以默认值结构存在（不得为 None）

#### 场景:加载非法字段时必须抛错

- **当** YAML 用例的 `level` 字段写成 `L5`（未声明的取值）
- **那么** Pydantic 校验必须失败，并以异常向上抛出，不允许吞掉错误后跳过该用例

#### 场景:残留的 case_version key 被忽略

- **当** 一条 YAML 用例仍带有历史遗留的 `case_version: v1` 键
- **那么** 加载 MUST 成功，生成的 `TestCase` 实例 MUST NOT 暴露 `case_version` 属性
