"""历史 outputs 导入工具测试。"""

from __future__ import annotations

from sqlalchemy import select

from factories import make_report

from server.db import session_scope
from server.import_history import import_outputs
from server.models_db import CaseResultRow, EvalRun


def test_import_outputs_idempotent(initialized_db, settings, tmp_path):
    outputs = tmp_path / "outputs"
    run_dir = outputs / "histrun_2026-06-01_1"
    run_dir.mkdir(parents=True)
    (run_dir / "report.json").write_text(
        make_report("histrun_2026-06-01_1").model_dump_json(), encoding="utf-8"
    )

    counts = import_outputs(outputs)
    assert counts["imported"] == 1

    with session_scope() as s:
        run = s.execute(select(EvalRun)).scalar_one()
        assert run.run_slug == "histrun_2026-06-01_1"
        assert run.total == 2
        assert s.execute(select(CaseResultRow)).scalars().all().__len__() == 2

    # 再次导入应跳过
    counts2 = import_outputs(outputs)
    assert counts2["skipped"] == 1
    assert counts2["imported"] == 0
