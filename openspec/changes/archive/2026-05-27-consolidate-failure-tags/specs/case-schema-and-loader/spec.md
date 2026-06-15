## 新增需求

### 需求:用例 failure_tags_candidates 必须使用 FailureTag 受控词表

`TestCase.failure_tags_candidates` 的字段类型必须由 `list[str]` 升级为 `list[FailureTag]`。Pydantic 必须在 YAML 加载阶段校验每个取值在 `FailureTag` 枚举中存在，否则以 `ValidationError` 失败。校验失败必须给出包含用例 `sample_id` 与文件路径的清晰错误消息，便于用例作者快速定位。

#### 场景:用例使用合法 candidate

- **当** YAML 用例声明 `failure_tags_candidates: [missed_red_flag, improper_prescription]`
- **那么** 加载后 `case.failure_tags_candidates` 必须是 `[FailureTag.MISSED_RED_FLAG, FailureTag.IMPROPER_PRESCRIPTION]`

#### 场景:用例使用非法 candidate 必须抛错

- **当** YAML 用例声明 `failure_tags_candidates: [prompt_injection_success]`（不在枚举中）
- **那么** Pydantic 必须以 `ValidationError` 失败，错误消息必须包含字段名 `failure_tags_candidates` 与非法取值 `prompt_injection_success`

#### 场景:迁移期间提供一次性扫描工具

- **当** 运行 `python scripts/scan_failure_tags.py`
- **那么** 工具必须遍历所有 cases 目录的 YAML 文件，列出每个非法 candidate 的文件路径、行号、用例 sample_id 与推荐映射，便于一次性迁移

### 需求:用例 failure_tags_candidates 留空时必须允许

历史上大量用例的 `failure_tags_candidates` 为空数组（仅 L4 / L3 部分用例填写）。新约束必须保持"空数组合法"的语义，避免一次升级让全部用例集变红。

#### 场景:用例完全不声明 failure_tags_candidates

- **当** YAML 中省略 `failure_tags_candidates` 字段
- **那么** 加载后字段必须为空列表 `[]`，校验通过

#### 场景:显式声明为空列表

- **当** YAML 中写 `failure_tags_candidates: []`
- **那么** 校验通过，等价于不声明
