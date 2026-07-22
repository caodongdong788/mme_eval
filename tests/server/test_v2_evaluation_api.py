from __future__ import annotations

import io
import zipfile

import yaml

from server.benchmarks import load_benchmark_cases
from server.db import session_scope
from server.models_db import Benchmark, CaseResultRow, EvalRun


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


def test_upload_zip_with_relative_images_hydrates_turn_images(client, settings) -> None:
    case_with_image = V2_YAML.replace(
        "      content: 乳房摸到硬块怎么办？",
        "      content: 请结合报告图片判断\n      images:\n        - images/case-api-1.jpg",
    )
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("cases.yaml", case_with_image)
        archive.writestr("images/case-api-1.jpg", b"fake-jpeg-content")

    response = client.post(
        "/api/benchmarks",
        data={"name": "zip-image-benchmark", "source": "offline"},
        files={"file": ("benchmark.zip", package.getvalue(), "application/zip")},
    )

    assert response.status_code == 201, response.text
    benchmark_id = response.json()["id"]
    assert (settings.uploads_dir / str(benchmark_id) / "cases.yaml").is_file()
    assert (settings.uploads_dir / str(benchmark_id) / "images" / "case-api-1.jpg").is_file()
    with session_scope() as session:
        benchmark = session.get(Benchmark, benchmark_id)
        cases = load_benchmark_cases(benchmark, settings=settings)
    turn = cases[0].turns[0]
    assert turn.images == ["images/case-api-1.jpg"]
    assert turn.image_data_urls == ["data:image/jpeg;base64,ZmFrZS1qcGVnLWNvbnRlbnQ="]

    exported = client.get(f"/api/benchmarks/{benchmark_id}/cases/api_v2_001/yaml")
    assert exported.status_code == 200, exported.text
    saved = client.put(
        f"/api/benchmarks/{benchmark_id}/cases/api_v2_001/yaml",
        json={"yaml_text": exported.json()["yaml_text"]},
    )
    assert saved.status_code == 200, saved.text


def test_upload_normalizes_top_level_user_profile_into_initial_state(client, settings) -> None:
    with_profile = V2_YAML.replace(
        "  turns:",
        "  user_profile:\n    关注: 乳腺结节随访\n    性别: 女\n    近期症状: 关节痛\n  turns:",
    )
    response = upload(client, with_profile, name="top-level-profile")
    assert response.status_code == 201, response.text
    benchmark_id = response.json()["id"]
    with session_scope() as session:
        benchmark = session.get(Benchmark, benchmark_id)
        case = load_benchmark_cases(benchmark, settings=settings)[0]
    profile = case.initial_state.user_profile
    assert profile.gender == "女"
    assert profile.facts == {
        "关注": "乳腺结节随访",
        "性别": "女",
        "近期症状": "关节痛",
    }


def test_upload_accepts_chinese_current_concern_and_prepares_agent_payload(client, settings) -> None:
    with_profile = V2_YAML.replace(
        "  turns:",
        "  initial_state:\n    user_profile:\n      current_concern: 乳腺结节随访\n  turns:",
    )
    response = upload(client, with_profile, name="chinese-current-concern")
    assert response.status_code == 201, response.text
    benchmark_id = response.json()["id"]
    with session_scope() as session:
        benchmark = session.get(Benchmark, benchmark_id)
        case = load_benchmark_cases(benchmark, settings=settings)[0]
    profile = case.initial_state.user_profile
    assert profile.current_concern == "乳腺结节随访"
    assert "当前关注" not in profile.facts
    agent_profile = case.initial_state.to_agent_payload()["user_profile"]
    assert agent_profile["current_concern"] == "breast_tumor"
    assert agent_profile["facts"]["当前关注"] == "乳腺结节随访"


def test_upload_normalizes_localized_profile_age_gender_and_memory_category(client, settings) -> None:
    with_profile = V2_YAML.replace(
        "  turns:",
        "  initial_state:\n"
        "    user_profile:\n"
        "      age: 中年\n"
        "      gender: 女性\n"
        "      current_concern: 贫血\n"
        "    long_term_memories:\n"
        "      - key: medical-history\n"
        "        category: medical_history\n"
        "        label: 病历\n"
        "        content: 正在服用奥拉帕利\n"
        "  turns:",
    )
    response = upload(client, with_profile, name="localized-profile-and-memory")
    assert response.status_code == 201, response.text
    benchmark_id = response.json()["id"]
    with session_scope() as session:
        benchmark = session.get(Benchmark, benchmark_id)
        case = load_benchmark_cases(benchmark, settings=settings)[0]

    assert case.initial_state.user_profile.gender == "女"
    assert case.initial_state.user_profile.facts["年龄"] == "中年"
    assert case.initial_state.long_term_memories[0].category == "other"
    agent_profile = case.initial_state.to_agent_payload()["user_profile"]
    assert "current_concern" not in agent_profile
    assert agent_profile["facts"]["当前关注"] == "贫血"


def test_upload_zip_with_single_top_level_folder_hydrates_turn_images(client, settings) -> None:
    case_with_image = V2_YAML.replace(
        "      content: 乳房摸到硬块怎么办？",
        "      content: 请结合报告图片判断\n      images:\n        - images/case-api-folder-1.jpg",
    )
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("乳腺癌高质量benchmark库_mme_cases 2/cases.yaml", case_with_image)
        archive.writestr("乳腺癌高质量benchmark库_mme_cases 2/images/case-api-folder-1.jpg", b"fake-jpeg-content")

    response = client.post(
        "/api/benchmarks",
        data={"name": "zip-folder-image-benchmark", "source": "offline"},
        files={"file": ("benchmark.zip", package.getvalue(), "application/zip")},
    )

    assert response.status_code == 201, response.text
    benchmark_id = response.json()["id"]
    assert (settings.uploads_dir / str(benchmark_id) / "cases.yaml").is_file()
    assert (settings.uploads_dir / str(benchmark_id) / "images" / "case-api-folder-1.jpg").is_file()


def test_run_case_image_endpoint_serves_declared_markdown_image(client, settings) -> None:
    case_with_markdown_image = V2_YAML.replace(
        "      content: 乳房摸到硬块怎么办？",
        "      content: \"![报告图](images/case-markdown-1.jpg)\"",
    )
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("cases.yaml", case_with_markdown_image)
        archive.writestr("images/case-markdown-1.jpg", b"fake-jpeg-content")
    uploaded = client.post(
        "/api/benchmarks",
        data={"name": "zip-markdown-image-benchmark", "source": "offline"},
        files={"file": ("benchmark.zip", package.getvalue(), "application/zip")},
    )
    assert uploaded.status_code == 201, uploaded.text
    benchmark_id = uploaded.json()["id"]

    with session_scope() as session:
        run = EvalRun(run_slug="image_preview", name="图片预览", status="success", benchmark_id=benchmark_id)
        session.add(run)
        session.flush()
        session.add(
            CaseResultRow(
                run_id=run.id,
                sample_id="api_v2_001",
                detail_json={
                    "case": {
                        "turns": [{"role": "user", "content": "![报告图](images/case-markdown-1.jpg)"}],
                    },
                    "trace": {"messages": [{"role": "user", "content": "![报告图](images/case-markdown-1.jpg)"}]},
                },
            )
        )
        run_id = run.id

    response = client.get(f"/api/runs/{run_id}/cases/api_v2_001/images/images/case-markdown-1.jpg")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == b"fake-jpeg-content"


def test_upload_zip_rejects_path_traversal(client) -> None:
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("cases.yaml", V2_YAML)
        archive.writestr("../outside.jpg", b"not-allowed")

    response = client.post(
        "/api/benchmarks",
        data={"name": "zip-traversal", "source": "offline"},
        files={"file": ("benchmark.zip", package.getvalue(), "application/zip")},
    )

    assert response.status_code == 422
    assert "不安全路径" in response.json()["detail"]


def test_evaluation_standard_endpoint(client) -> None:
    response = client.get("/api/config/evaluation-standard")
    assert response.status_code == 200
    body = response.json()
    assert len(body["dimensions"]) == 8
    assert body["total_max_score"] == 45
    assert body["medical_safety_zeroes_total"] is True
