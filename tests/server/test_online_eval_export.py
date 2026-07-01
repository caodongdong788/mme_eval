from __future__ import annotations

from openpyxl import load_workbook

from server.db import session_scope
from server.models_db import OnlineEval, OnlineEvalCase
from server.services.online_eval_export import case_dialogue_turns, split_filter_values


def _seed_online_eval() -> int:
    with session_scope() as session:
        row = OnlineEval(
            name="导出批次",
            status="success",
            case_count=2,
            avg_score_10=7.2,
        )
        row.cases.append(
            OnlineEvalCase(
                external_id="case-pass",
                case_name="骨密度复诊咨询",
                user_text="第一问\n第二问",
                assistant_text="第一答\n第二答",
                raw_messages=[
                    {"role": "user", "content": "第一问"},
                    {"role": "assistant", "content": "第一答"},
                    {"role": "user", "content": "第二问"},
                    {"role": "assistant", "content": "第二答"},
                ],
                gate_status="pass",
                total_score_10=9.2,
                grade="excellent",
                task_type="report_interpretation",
            )
        )
        row.cases.append(
            OnlineEvalCase(
                external_id="case-fail",
                case_name="停药建议",
                user_text="能不能停药",
                assistant_text="可以自行停药",
                raw_messages=[
                    {"role": "user", "content": "能不能停药"},
                    {"role": "assistant", "content": "可以自行停药"},
                ],
                gate_status="fail",
                total_score_10=5.0,
                grade="fail",
                task_type="adherence_side_effect",
            )
        )
        session.add(row)
        session.flush()
        return row.id


def test_online_eval_export_filters_and_writes_multiturn_xlsx(client, monkeypatch):
    eval_id = _seed_online_eval()
    captured: dict = {}

    def fake_publish(xlsx_path, *, parent_folder_token, title):
        captured["folder"] = parent_folder_token
        captured["title"] = title
        wb = load_workbook(xlsx_path)
        ws = wb.active
        captured["rows"] = [tuple(row) for row in ws.iter_rows(values_only=True)]
        return "https://feishu.example/sheets/online-export"

    monkeypatch.setattr(
        "server.services.online_eval_export.publish_xlsx_to_lark", fake_publish
    )

    resp = client.post(
        f"/api/online-evals/{eval_id}/export-cases",
        params={
            "gate_status": "pass",
            "score_bucket": "gte9",
            "grade": "excellent",
            "parent_folder_token": "",
        },
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["url"] == "https://feishu.example/sheets/online-export"
    assert resp.json()["count"] == 1
    assert captured["folder"] == ""
    assert captured["title"] == "导出批次_评测清单"
    assert captured["rows"][0] == (
        "会话标题",
        "第一轮用户输入",
        "第一轮Cx输出",
        "第二轮用户输入",
        "第二轮Cx输出",
    )
    assert captured["rows"][1] == ("骨密度复诊咨询", "第一问", "第一答", "第二问", "第二答")


def test_online_eval_export_empty_filter_returns_400(client, monkeypatch):
    eval_id = _seed_online_eval()

    monkeypatch.setattr(
        "server.services.online_eval_export.publish_xlsx_to_lark",
        lambda *args, **kwargs: "https://feishu.example/sheets/unused",
    )

    resp = client.post(
        f"/api/online-evals/{eval_id}/export-cases",
        params={"gate_status": "pass", "grade": "fail"},
    )

    assert resp.status_code == 400
    assert "没有可导出" in resp.json()["detail"]


def test_case_dialogue_turns_falls_back_to_flat_text(session):
    case = OnlineEvalCase(
        user_text="单轮用户",
        assistant_text="单轮回答",
        raw_messages=[],
        gate_status="pass",
        total_score_10=8.0,
        grade="high_quality",
    )

    assert case_dialogue_turns(case) == [("单轮用户", "单轮回答")]


def test_split_filter_values_trims_blanks():
    assert split_filter_values(" pass, fail ,,") == ["pass", "fail"]
