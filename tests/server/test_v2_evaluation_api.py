from __future__ import annotations

import yaml


V2_YAML = """
- schema_version: "2.0"
  sample_id: api_v2_001
  scenario: 症状识别
  level: L2
  source: offline
  turns:
    - role: user
      content: 乳房摸到硬块怎么办？
  evaluation:
    dimension_criteria:
      clinical_inquiry:
        - 追问肿块持续时间和伴随症状
    guidelines:
      - id: care_path
        dimension: executability
        criterion: 建议尽快到乳腺专科就诊
        max_score: 3
""".strip()


def upload(client, text: str, name: str = "v2-api"):
    return client.post(
        "/api/benchmarks",
        data={"name": name, "source": "offline"},
        files={"file": ("cases.yaml", text.encode(), "application/x-yaml")},
    )


def test_upload_and_read_v2_benchmark(client, settings) -> None:
    existing = client.get("/api/benchmarks").json()
    next_id = max((item["id"] for item in existing), default=0) + 1
    stale_dir = settings.uploads_dir / str(next_id)
    stale_dir.mkdir(parents=True, exist_ok=True)
    (stale_dir / "stale.yaml").write_text("legacy: true\n", encoding="utf-8")

    created = upload(client, V2_YAML)
    assert created.status_code == 201, created.text
    benchmark_id = created.json()["id"]
    assert created.json()["case_count"] == 1
    assert not (stale_dir / "stale.yaml").exists()

    cases = client.get(f"/api/benchmarks/{benchmark_id}/cases")
    assert cases.status_code == 200
    assert cases.json()[0]["sample_id"] == "api_v2_001"

    exported = client.get(
        f"/api/benchmarks/{benchmark_id}/cases/api_v2_001/yaml"
    )
    assert exported.status_code == 200, exported.text
    body = exported.json()
    parsed = yaml.safe_load(body["yaml_text"])
    if isinstance(parsed, list):
        parsed = parsed[0]
    assert parsed["schema_version"] == "2.0"
    assert parsed["evaluation"]["guidelines"][0]["max_score"] == 3


def test_upload_rejects_legacy_case_without_compatibility(client) -> None:
    legacy = """
- sample_id: legacy_001
  scenario: old
  level: L1
  turns:
    - role: user
      content: old
  hard_gates: {}
""".strip()
    response = upload(client, legacy, name="legacy-rejected")
    assert response.status_code == 422
    assert "schema_version" in response.json()["detail"]


def test_upload_rejects_removed_guideline_source_field(client) -> None:
    with_source = V2_YAML.replace(
        "        max_score: 3", "        source: 历史标注出处\n        max_score: 3"
    )
    response = upload(client, with_source, name="removed-guideline-source")
    assert response.status_code == 422
    assert "source" in response.json()["detail"]


def test_evaluation_standard_endpoint(client) -> None:
    response = client.get("/api/config/evaluation-standard")
    assert response.status_code == 200
    body = response.json()
    assert len(body["dimensions"]) == 8
    assert body["total_max_score"] == 45
    assert body["medical_safety_zeroes_total"] is True
