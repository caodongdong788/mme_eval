"""历史指南判分异常的列表/详情回填。"""

from __future__ import annotations

from server import db as db_mod
from server.models_db import CaseResultRow, EvalRun


def test_migrates_historical_guideline_judge_error(initialized_db, session) -> None:
    run = EvalRun(run_slug="legacy-guideline-error")
    session.add(run)
    session.flush()
    row = CaseResultRow(
        run_id=run.id,
        sample_id="case_1",
        grade="不合格",
        composite_score=0,
        medical_safety_passed=False,
        release_passed=False,
        failure_tags=["medical_safety_risk"],
        detail_json={
            "verdicts": [
                {
                    "name": "guideline.safety",
                    "reason": "指南判分失败：Expecting value: line 1 column 1",
                    "details": {"deduction": 5},
                }
            ],
            "guideline_scores": [{"id": "safety", "score": 0, "max_score": 5}],
        },
    )
    session.add(row)
    session.commit()

    db_mod._migrate_case_judge_error(db_mod.init_engine(initialized_db))
    session.expire_all()
    migrated = session.get(CaseResultRow, row.id)

    assert migrated is not None
    assert migrated.judge_error is True
    assert migrated.grade == "判分异常"
    assert migrated.composite_score is None
    assert migrated.failure_tags == []
    assert migrated.detail_json["guideline_scores"][0]["judge_error"] is True
    assert "指南判分失败" in migrated.detail_json["guideline_scores"][0]["judge_error_message"]


def test_migrates_historical_invalid_guideline_deduction_to_judge_error(initialized_db, session) -> None:
    run = EvalRun(run_slug="legacy-invalid-guideline-deduction")
    session.add(run)
    session.flush()
    row = CaseResultRow(
        run_id=run.id,
        sample_id="case_1",
        grade="不合格",
        composite_score=0,
        medical_safety_passed=False,
        release_passed=False,
        failure_tags=["medical_safety_risk"],
        detail_json={
            "verdicts": [{
                "name": "guideline.plan",
                "reason": "模型返回非法扣分 None，保守按最多扣分",
                "details": {"deduction": 1, "model_deduction": None},
            }],
            "guideline_scores": [{"id": "plan", "score": 0, "max_score": 1}],
        },
    )
    session.add(row)
    session.commit()

    db_mod._migrate_case_judge_error(db_mod.init_engine(initialized_db))
    session.expire_all()
    migrated = session.get(CaseResultRow, row.id)

    assert migrated is not None
    assert migrated.judge_error is True
    assert migrated.grade == "判分异常"
    assert migrated.detail_json["guideline_scores"][0]["judge_error"] is True
    assert "非法扣分" in migrated.detail_json["guideline_scores"][0]["judge_error_message"]
