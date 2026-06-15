"""GET /api/config/judge-verdict-labels"""


def test_judge_verdict_labels_endpoint(client, settings):
    resp = client.get("/api/config/judge-verdict-labels")
    assert resp.status_code == 200
    data = resp.json()
    assert data["hard_gate.red_flag"] == "硬门槛·红旗分诊"
    assert data["llm.empathy"] == "体验·共情"
    assert data["llm.triage_quality"] == "体验·分诊建议"
