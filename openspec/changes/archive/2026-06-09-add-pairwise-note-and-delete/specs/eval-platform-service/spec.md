# eval-platform-service (delta)

## ADDED Requirements

### Requirement: Pairwise 对比备注

每次 Pairwise 对比 MUST 可携带一段自由文本备注 `note`（对比目的），默认空串。发起接口
`POST /api/compare/pairwise` MUST 接受可选 `note` 并持久化；读取/列表接口 MUST 回显 `note`。
系统 MUST 提供 `PATCH /api/compare/pairwise/{id}` 二次编辑 `note`（对不存在的 id 返回 404），
且该接口 MUST NOT 改动除 `note` 外的任何字段（不影响判分、汇总、可比性）。

#### Scenario: 发起时写入备注并回显

- **WHEN** 以 `note="验证 v6 prompt 收紧后安全是否退化"` 发起对比
- **THEN** 该对比记录 MUST 持久化该 `note`，列表与详情接口 MUST 回显相同 `note`

#### Scenario: 二次编辑备注

- **WHEN** 对已存在的对比 `PATCH` 一个新的 `note`
- **THEN** 该对比的 `note` MUST 被更新为新值，其余字段 MUST 保持不变

### Requirement: 删除 Pairwise 对比

系统 MUST 提供 `DELETE /api/compare/pairwise/{id}` 物理删除一次对比记录，并 MUST 级联删除其
全部逐用例结论（`PairwiseCaseVerdict`）。删除成功 MUST 返回 204；对不存在的 id MUST 返回 404。

#### Scenario: 删除连带清空 verdict

- **WHEN** 删除一个已有逐用例结论的对比
- **THEN** 该对比记录与其全部 `PairwiseCaseVerdict` MUST 被一并删除，后续查询 MUST 返回 404
