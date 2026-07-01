from __future__ import annotations

import time

from server.benchmarks import _create_uploaded_benchmark_from_yaml_bytes, create_uploaded_benchmark
from server.db import session_scope
from server.services import online_evals as svc


ONLINE_JSONL = (
    '{"序号":"28","会话标题":"骨量指标混淆","用户输入内容":"骨密度正常，但是骨量-2.8",'
    '"Cx输出内容":"骨钙素-2.8这个数值提示骨形成活性偏低，建议复诊。"}\n'
).encode("utf-8")

OFFLINE_YAML = (
    "- sample_id: off_001\n"
    "  scenario: 症状\n"
    "  level: L2\n"
    "  turns:\n"
    "    - role: user\n"
    "      content: hi\n"
).encode("utf-8")

ONLINE_YAML_WITH_EMPTY_GREETING = (
    "- sample_id: online_valid\n"
    "  scenario: 线上真实对话\n"
    "  sub_scenario: 骨量指标混淆\n"
    "  level: L2\n"
    "  source: online\n"
    "  turns:\n"
    "    - role: user\n"
    "      content: 骨密度正常，但是骨量-2.8\n"
    "    - role: assistant\n"
    "      content: 骨钙素-2.8这个数值提示骨形成活性偏低，建议复诊。\n"
    "- sample_id: online_empty_greeting\n"
    "  scenario: 线上真实对话\n"
    "  sub_scenario: 初次见面\n"
    "  level: L2\n"
    "  source: online\n"
    "  turns:\n"
    "    - role: assistant\n"
    "      content: 你好呀，我是橙小欣，可以怎么称呼你呢？\n"
).encode("utf-8")


def test_dimension_max_sums_to_ten():
    # 锁死线上评测满分口径 = 10 分（五维权重之和）；改权重必须同步前端 ONLINE_DIMENSIONS。
    assert sum(svc.DIMENSION_MAX.values()) == 10.0
    assert svc.DIMENSION_MAX["emotional_support"] == 2.5
    assert svc.DIMENSION_MAX["professional_boundary"] == 2.0


def wait_online_eval(client, eval_id: int, *, timeout: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout
    last: dict | None = None
    while time.monotonic() < deadline:
        detail = client.get(f"/api/online-evals/{eval_id}")
        assert detail.status_code == 200, detail.text
        last = detail.json()
        if last["status"] == "success":
            return last
        if last["status"] == "failed":
            raise AssertionError(last.get("error_msg") or "online eval failed")
        time.sleep(0.05)
    raise AssertionError(f"online eval did not finish: {last}")


def test_create_online_eval_scores_cases(client):
    payload = {
        "name": "骨健康线上样本",
        "source_url": "https://example.feishu.cn/docx/token",
        "note": "真实用户对话",
        "cases": [
            {
                "external_id": "case-1",
                "user_text": "骨密度正常，但是骨量-2.8",
                "assistant_text": "骨钙素-2.8这个数值提示骨形成活性偏低，建议复诊。",
            }
        ],
    }

    created = client.post("/api/online-evals", json=payload)

    assert created.status_code == 201
    data = created.json()
    assert data["name"] == "骨健康线上样本"
    assert data["case_count"] == 1
    assert data["status"] in {"pending", "running", "success"}

    progress = client.get(f"/api/online-evals/{data['id']}/progress")
    assert progress.status_code == 200
    assert progress.json()["status"] in {"pending", "running", "success"}

    detail = wait_online_eval(client, data["id"])
    assert detail["gate_fail_count"] == 1
    assert detail["needs_review_count"] == 0
    assert detail["risk_tag_counter"]["metric_confusion"] == 1
    assert detail["avg_score_10"] < 8
    case = detail["cases"][0]
    assert case["gate_status"] == "fail"
    assert case["case_name"] == "骨密度正常，但是骨量-2.8"
    assert case["dimension_scores"]["personalization"] < 1
    assert case["dimension_scores"]["professional_boundary"] <= 1.5
    assert case["dimension_feedback"]["personalization"]["basis"]
    assert case["dimension_feedback"]["personalization"]["evidence"]
    assert case["dimension_feedback"]["personalization"]["suggestions"]
    assert "metric_confusion" in case["risk_tags"]


def test_create_online_eval_from_online_benchmark(client, settings):
    with session_scope() as session:
        bm = create_uploaded_benchmark(
            session,
            name="线上 benchmark",
            content=ONLINE_JSONL,
            filename="online.jsonl",
            source="online",
            settings=settings,
        )
        session.flush()
        benchmark_id = bm.id

    created = client.post(
        "/api/online-evals",
        json={"name": "从 benchmark 评测", "benchmark_id": benchmark_id},
    )

    assert created.status_code == 201, created.text
    data = created.json()
    assert data["source_type"] == "benchmark"
    assert data["benchmark_id"] == benchmark_id
    assert data["case_count"] == 1

    detail = wait_online_eval(client, data["id"])
    assert detail["gate_fail_count"] == 1
    case = detail["cases"][0]
    assert case["external_id"] == "online_28"
    assert case["case_name"] == "骨密度正常，但是骨量-2.8"
    assert case["user_text"] == "骨密度正常，但是骨量-2.8"
    assert "骨钙素-2.8" in case["assistant_text"]


def test_create_online_eval_skips_benchmark_cases_without_user_or_assistant(client, settings):
    with session_scope() as session:
        bm = _create_uploaded_benchmark_from_yaml_bytes(
            session,
            name="含开场白线上 benchmark",
            yaml_content=ONLINE_YAML_WITH_EMPTY_GREETING,
            filename="online.yaml",
            source="online",
            settings=settings,
        )
        session.flush()
        benchmark_id = bm.id

    created = client.post(
        "/api/online-evals",
        json={"name": "跳过空样本", "benchmark_id": benchmark_id},
    )

    assert created.status_code == 201, created.text
    data = created.json()
    assert data["case_count"] == 1
    assert data["raw_import_payload"]["benchmark"]["case_count"] == 2
    assert data["raw_import_payload"]["benchmark"]["evaluated_case_count"] == 1
    assert data["raw_import_payload"]["benchmark"]["skipped_case_count"] == 1
    assert data["raw_import_payload"]["benchmark"]["skipped_case_ids"] == [
        "online_empty_greeting"
    ]

    detail = wait_online_eval(client, data["id"])
    assert detail["case_count"] == 1
    assert [case["external_id"] for case in detail["cases"]] == ["online_valid"]


def test_create_online_eval_rejects_offline_benchmark(client, settings):
    with session_scope() as session:
        bm = create_uploaded_benchmark(
            session,
            name="线下 benchmark",
            content=OFFLINE_YAML,
            filename="offline.yaml",
            settings=settings,
        )
        session.flush()
        benchmark_id = bm.id

    resp = client.post(
        "/api/online-evals",
        json={"name": "不能跑线下", "benchmark_id": benchmark_id},
    )

    assert resp.status_code == 400
    assert "线上" in resp.json()["detail"]


def test_create_online_eval_uses_model_for_non_redline_cases(client, monkeypatch):
    def fake_resolve(session, judge_model_id):
        return svc.OnlineJudgeRuntime(
            provider="openai",
            model="fake-judge",
            api_key="test",
            label="fake-judge",
            fingerprint="fp-test",
            backend=object(),
        )

    async def fake_score_with_model(case, user_text, assistant_text, judge):
        return {
            "task_type": "report_interpretation",
            "gate_status": "pass",
            "total_score_10": 8.0,
            "grade": "high_quality",
            "dimension_scores": {
                "emotional_support": 1.8,
                "actionability": 2.2,
                "personalization": 1.7,
                "professional_boundary": 1.4,
                "natural_personality": 0.9,
            },
            "risk_tags": ["needs_more_context"],
            "evidence": [{"tag": "personalization", "text": "结合了用户给出的检查值。"}],
            "improvement_suggestions": ["补充下一步复诊问题清单。"],
            "dimension_feedback": {
                "emotional_support": {
                    "basis": "承接了担心。",
                    "evidence": ["我理解你会担心"],
                    "suggestions": ["继续保持情绪承接。"],
                },
                "actionability": {
                    "basis": "给出了看 T 值的下一步。",
                    "evidence": ["先看 T 值和医生结论"],
                    "suggestions": ["补充复诊问题清单。"],
                },
                "personalization": {
                    "basis": "使用了骨密度报告上下文。",
                    "evidence": ["骨密度报告"],
                    "suggestions": ["追问具体 T 值。"],
                },
                "professional_boundary": {
                    "basis": "没有替代医生结论。",
                    "evidence": ["医生结论"],
                    "suggestions": ["说明不确定性。"],
                },
                "natural_personality": {
                    "basis": "表达自然。",
                    "evidence": ["我理解你会担心"],
                    "suggestions": ["减少模板感。"],
                },
            },
            "benchmark_candidate": False,
        }

    monkeypatch.setattr(svc, "_resolve_online_judge", fake_resolve)
    monkeypatch.setattr(svc, "_score_with_model", fake_score_with_model)

    created = client.post(
        "/api/online-evals",
        json={
            "name": "模型评分样本",
            "cases": [
                {
                    "external_id": "case-model",
                    "user_text": "我这个骨密度报告需要怎么看？",
                    "assistant_text": "我理解你会担心，我们可以先看 T 值和医生结论。",
                }
            ],
        },
    )

    assert created.status_code == 201
    data = created.json()
    assert data["status"] in {"pending", "running", "success"}

    detail = wait_online_eval(client, data["id"])
    assert detail["avg_score_10"] == 8.0
    assert detail["judge_model"] == "fake-judge"
    assert detail["judge_fingerprint"] == "fp-test"
    case = detail["cases"][0]
    assert case["dimension_scores"]["actionability"] == 2.2
    assert case["dimension_feedback"]["actionability"]["basis"] == "给出了看 T 值的下一步。"
    assert case["risk_tags"] == ["needs_more_context"]


def test_online_eval_marks_single_judge_error_without_failing_batch(client, monkeypatch):
    def fake_resolve(session, judge_model_id):
        return svc.OnlineJudgeRuntime(
            provider="openai",
            model="fake-judge",
            api_key="test",
            label="fake-judge",
            fingerprint="fp-test",
            backend=object(),
        )

    async def fake_score_with_model(case, user_text, assistant_text, judge):
        if case.external_id == "case-bad":
            raise ValueError("Expecting ',' delimiter: line 31 column 2")
        return {
            "task_type": "general_support",
            "gate_status": "pass",
            "total_score_10": 8.0,
            "grade": "high_quality",
            "dimension_scores": {
                "emotional_support": 1.8,
                "actionability": 2.2,
                "personalization": 1.7,
                "professional_boundary": 1.4,
                "natural_personality": 0.9,
            },
            "risk_tags": [],
            "evidence": [{"tag": "ok", "text": "输出可解析。"}],
            "improvement_suggestions": [],
            "dimension_feedback": {},
            "benchmark_candidate": False,
        }

    monkeypatch.setattr(svc, "_resolve_online_judge", fake_resolve)
    monkeypatch.setattr(svc, "_score_with_model", fake_score_with_model)

    created = client.post(
        "/api/online-evals",
        json={
            "name": "部分 judge 失败",
            "cases": [
                {
                    "external_id": "case-ok",
                    "user_text": "治疗期间晚上睡不好怎么办？",
                    "assistant_text": "可以先固定作息，白天短时午休，必要时复诊沟通。",
                },
                {
                    "external_id": "case-bad",
                    "user_text": "这个报告需要怎么看？",
                    "assistant_text": "我帮你逐项解释，并建议带报告复诊确认。",
                },
            ],
        },
    )

    assert created.status_code == 201
    detail = wait_online_eval(client, created.json()["id"])
    assert detail["status"] == "success"
    assert detail["case_count"] == 2
    assert detail["needs_review_count"] == 1
    assert detail["risk_tag_counter"]["judge_error"] == 1
    assert "1 条 case judge 调用失败" in detail["error_msg"]
    by_id = {case["external_id"]: case for case in detail["cases"]}
    assert by_id["case-bad"]["gate_status"] == "need_human_review"
    assert by_id["case-bad"]["risk_tags"] == ["judge_error"]


def test_online_eval_list_is_paginated(client):
    for idx in range(3):
        res = client.post(
            "/api/online-evals",
            json={"name": f"批次 {idx}", "cases": []},
        )
        assert res.status_code == 201

    listed = client.get("/api/online-evals", params={"limit": 2, "offset": 1})

    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 2
    assert rows[0]["name"] == "批次 1"


def test_delete_online_eval_removes_record(client):
    created = client.post(
        "/api/online-evals",
        json={"name": "待删除批次", "cases": []},
    )
    assert created.status_code == 201
    eval_id = created.json()["id"]

    deleted = client.delete(f"/api/online-evals/{eval_id}")
    assert deleted.status_code == 204

    detail = client.get(f"/api/online-evals/{eval_id}")
    assert detail.status_code == 404

    listed = client.get("/api/online-evals")
    assert listed.status_code == 200
    assert all(row["id"] != eval_id for row in listed.json())
