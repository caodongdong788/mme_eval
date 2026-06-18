# Tasks: standardize-rubric-points-anchors

- [x] 盘点 18 处 `rubric.points`（agent 4 + multi_turn 13 + adversarial 1）
- [x] 改写为三档/两档显式 `"N 分=…"` 句式
- [x] 更新 `cases/README.md` 对比说明
- [x] `pytest tests/test_loader.py`（或等效 loader 校验）
- [ ] `openspec validate --strict` + archive
