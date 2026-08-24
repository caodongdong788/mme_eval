from __future__ import annotations

import io
import zipfile
from datetime import datetime
from pathlib import Path

import yaml

from server.benchmarks import load_benchmark_cases
from server.db import session_scope
from server.models_db import Benchmark, CaseResultRow, EvalRun
from server.services.eval_artifacts import snapshot_case_images


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


def _reset_benchmark_updated_at(benchmark_id: int) -> datetime:
    baseline = datetime(2000, 1, 1)
    with session_scope() as session:
        benchmark = session.get(Benchmark, benchmark_id)
        assert benchmark is not None
        benchmark.updated_at = baseline
    return baseline


def _assert_benchmark_touched(client, benchmark_id: int, baseline: datetime) -> None:
    body = client.get(f"/api/benchmarks/{benchmark_id}").json()
    assert body["created_at"]
    assert body["updated_at"]
    assert datetime.fromisoformat(body["updated_at"].replace("Z", "+00:00")).replace(
        tzinfo=None
    ) > baseline


def test_upload_and_read_v2_benchmark(client, settings) -> None:
    existing = client.get("/api/benchmarks").json()
    next_id = max((item["id"] for item in existing), default=0) + 1
    stale_dir = settings.uploads_dir / str(next_id)
    stale_dir.mkdir(parents=True, exist_ok=True)
    (stale_dir / "stale.yaml").write_text("legacy: true\n", encoding="utf-8")

    yaml_with_case_metadata = V2_YAML.replace(
        "  scenario: 症状识别",
        "  scenario: 症状识别\n  case_type: 医学诊疗类\n  is_bug: 产品优化",
    )
    created = upload(client, yaml_with_case_metadata)
    assert created.status_code == 201, created.text
    benchmark_id = created.json()["id"]
    assert created.json()["case_count"] == 1
    assert not (stale_dir / "stale.yaml").exists()

    cases = client.get(f"/api/benchmarks/{benchmark_id}/cases")
    assert cases.status_code == 200
    assert cases.json()[0]["sample_id"] == "api_v2_001"
    assert cases.json()[0]["case_type"] == "医学诊疗类"
    assert cases.json()[0]["is_bug"] == "产品优化"

    exported = client.get(
        f"/api/benchmarks/{benchmark_id}/cases/api_v2_001/yaml"
    )
    assert exported.status_code == 200, exported.text
    body = exported.json()
    parsed = yaml.safe_load(body["yaml_text"])
    if isinstance(parsed, list):
        parsed = parsed[0]
    assert parsed["schema_version"] == "2.0"
    assert parsed["case_type"] == "医学诊疗类"
    assert parsed["is_bug"] == "产品优化"
    assert parsed["evaluation"]["guidelines"][0]["max_score"] == 3


def test_append_yaml_cases_to_existing_benchmark(client, settings) -> None:
    created = upload(client, V2_YAML, name="append-yaml-target")
    benchmark_id = created.json()["id"]
    appended_yaml = V2_YAML.replace("api_v2_001", "api_v2_002").replace(
        "scenario: 症状识别", "scenario: 复诊管理"
    )

    response = client.post(
        f"/api/benchmarks/{benchmark_id}/append",
        data={"source": "offline"},
        files={"file": ("more.yaml", appended_yaml.encode(), "application/x-yaml")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["case_count"] == 2
    assert response.json()["name"] == "append-yaml-target"
    cases = client.get(f"/api/benchmarks/{benchmark_id}/cases").json()
    assert [case["sample_id"] for case in cases] == ["api_v2_001", "api_v2_002"]
    exported = client.get(f"/api/benchmarks/{benchmark_id}/download")
    assert {item["sample_id"] for item in yaml.safe_load(exported.text)} == {
        "api_v2_001",
        "api_v2_002",
    }
    assert (settings.uploads_dir / str(benchmark_id) / "cases.yaml").is_file()


def test_all_benchmark_mutations_refresh_updated_at(client) -> None:
    created = upload(client, V2_YAML, name="timestamp-target")
    assert created.status_code == 201, created.text
    benchmark_id = created.json()["id"]
    assert created.json()["created_at"]
    assert created.json()["updated_at"]

    baseline = _reset_benchmark_updated_at(benchmark_id)
    edited = client.patch(
        f"/api/benchmarks/{benchmark_id}",
        json={"description": "人工更新说明"},
    )
    assert edited.status_code == 200, edited.text
    _assert_benchmark_touched(client, benchmark_id, baseline)

    baseline = _reset_benchmark_updated_at(benchmark_id)
    case_content = client.get(
        f"/api/benchmarks/{benchmark_id}/cases/api_v2_001/content"
    ).json()["case"]
    case_content["notes"] = "人工修改 Case"
    saved = client.put(
        f"/api/benchmarks/{benchmark_id}/cases/api_v2_001/content",
        json={"case": case_content},
    )
    assert saved.status_code == 200, saved.text
    _assert_benchmark_touched(client, benchmark_id, baseline)

    baseline = _reset_benchmark_updated_at(benchmark_id)
    source_yaml = client.get(
        f"/api/benchmarks/{benchmark_id}/cases/api_v2_001/yaml"
    ).json()["yaml_text"]
    saved_yaml = client.put(
        f"/api/benchmarks/{benchmark_id}/cases/api_v2_001/yaml",
        json={"yaml_text": source_yaml},
    )
    assert saved_yaml.status_code == 200, saved_yaml.text
    _assert_benchmark_touched(client, benchmark_id, baseline)

    baseline = _reset_benchmark_updated_at(benchmark_id)
    appended_yaml = V2_YAML.replace("api_v2_001", "api_v2_002")
    appended = client.post(
        f"/api/benchmarks/{benchmark_id}/append",
        data={"source": "offline"},
        files={"file": ("more.yaml", appended_yaml.encode(), "application/x-yaml")},
    )
    assert appended.status_code == 200, appended.text
    _assert_benchmark_touched(client, benchmark_id, baseline)

    baseline = _reset_benchmark_updated_at(benchmark_id)
    overwritten = client.post(
        f"/api/benchmarks/{benchmark_id}/overwrite-yaml",
        json={"yaml_text": appended_yaml},
    )
    assert overwritten.status_code == 200, overwritten.text
    _assert_benchmark_touched(client, benchmark_id, baseline)

    baseline = _reset_benchmark_updated_at(benchmark_id)
    replaced = client.put(
        f"/api/benchmarks/{benchmark_id}",
        data={"source": "offline"},
        files={"file": ("replacement.yaml", V2_YAML.encode(), "application/x-yaml")},
    )
    assert replaced.status_code == 200, replaced.text
    _assert_benchmark_touched(client, benchmark_id, baseline)

    # 重新追加一条后删除，验证人工删除 Case 同样刷新时间。
    client.post(
        f"/api/benchmarks/{benchmark_id}/append",
        data={"source": "offline"},
        files={"file": ("more.yaml", appended_yaml.encode(), "application/x-yaml")},
    )
    baseline = _reset_benchmark_updated_at(benchmark_id)
    deleted = client.delete(f"/api/benchmarks/{benchmark_id}/cases/api_v2_002")
    assert deleted.status_code == 204, deleted.text
    _assert_benchmark_touched(client, benchmark_id, baseline)


def test_append_rejects_duplicate_sample_id_without_changing_target(client) -> None:
    created = upload(client, V2_YAML, name="append-duplicate-target")
    benchmark_id = created.json()["id"]

    response = client.post(
        f"/api/benchmarks/{benchmark_id}/append",
        data={"source": "offline"},
        files={"file": ("duplicate.yaml", V2_YAML.encode(), "application/x-yaml")},
    )

    assert response.status_code == 422
    assert "sample_id 与现有用例重复" in response.json()["detail"]
    cases = client.get(f"/api/benchmarks/{benchmark_id}/cases").json()
    assert [case["sample_id"] for case in cases] == ["api_v2_001"]


def test_append_zip_cases_and_images_to_existing_benchmark(client, settings) -> None:
    created = upload(client, V2_YAML, name="append-zip-target")
    benchmark_id = created.json()["id"]
    appended_yaml = V2_YAML.replace("api_v2_001", "api_v2_image_002").replace(
        "      content: 乳房摸到硬块怎么办？",
        "      content: 请结合追加的报告图片判断\n      images:\n        - images/appended.jpg",
    )
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("cases.yaml", appended_yaml)
        archive.writestr("images/appended.jpg", b"appended-image")

    response = client.post(
        f"/api/benchmarks/{benchmark_id}/append",
        data={"source": "offline"},
        files={"file": ("more.zip", package.getvalue(), "application/zip")},
    )

    assert response.status_code == 200, response.text
    assert response.json()["case_count"] == 2
    assert (
        settings.uploads_dir / str(benchmark_id) / "images" / "appended.jpg"
    ).read_bytes() == b"appended-image"
    with session_scope() as session:
        benchmark = session.get(Benchmark, benchmark_id)
        cases = load_benchmark_cases(benchmark, settings=settings)
    assert cases[1].turns[0].image_data_urls


def test_append_zip_rejects_existing_image_path(client, settings) -> None:
    original_yaml = V2_YAML.replace(
        "      content: 乳房摸到硬块怎么办？",
        "      content: 原报告\n      images:\n        - images/shared.jpg",
    )
    original = io.BytesIO()
    with zipfile.ZipFile(original, "w") as archive:
        archive.writestr("cases.yaml", original_yaml)
        archive.writestr("images/shared.jpg", b"original-image")
    created = client.post(
        "/api/benchmarks",
        data={"name": "append-image-conflict", "source": "offline"},
        files={"file": ("original.zip", original.getvalue(), "application/zip")},
    )
    benchmark_id = created.json()["id"]

    appended_yaml = original_yaml.replace("api_v2_001", "api_v2_002")
    appended = io.BytesIO()
    with zipfile.ZipFile(appended, "w") as archive:
        archive.writestr("cases.yaml", appended_yaml)
        archive.writestr("images/shared.jpg", b"replacement-image")
    response = client.post(
        f"/api/benchmarks/{benchmark_id}/append",
        data={"source": "offline"},
        files={"file": ("more.zip", appended.getvalue(), "application/zip")},
    )

    assert response.status_code == 422
    assert "图片路径与现有文件重复" in response.json()["detail"]
    assert (
        settings.uploads_dir / str(benchmark_id) / "images" / "shared.jpg"
    ).read_bytes() == b"original-image"
    assert client.get(f"/api/benchmarks/{benchmark_id}").json()["case_count"] == 1


def test_read_and_save_structured_case_content(client) -> None:
    """结构化编辑器无需前端解析 YAML，也能完整读取并写回单条 Case。"""
    created = upload(client, V2_YAML, name="structured-case")
    benchmark_id = created.json()["id"]

    read = client.get(f"/api/benchmarks/{benchmark_id}/cases/api_v2_001/content")
    assert read.status_code == 200, read.text
    body = read.json()
    assert body["case"]["scenario"] == "症状识别"
    assert body["case"]["evaluation"]["dimension_criteria"]["clinical_inquiry"]

    edited = body["case"]
    edited["scenario"] = "症状识别（已编辑）"
    edited.setdefault("initial_state", {})["user_profile"] = {"性别": "女"}
    edited["evaluation"]["guidelines"][0]["criterion"] = ["应尽快到乳腺专科就诊"]
    saved = client.put(
        f"/api/benchmarks/{benchmark_id}/cases/api_v2_001/content",
        json={"case": edited},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["case"]["scenario"] == "症状识别（已编辑）"
    assert saved.json()["case"]["initial_state"]["user_profile"]["性别"] == "女"


def test_upload_and_read_v21_reference_answers(client) -> None:
    v21_yaml = V2_YAML.replace('schema_version: "2.0"', 'schema_version: "2.1"').replace(
        "      clinical_inquiry:\n        - 追问肿块持续时间和伴随症状",
        "      clinical_inquiry:\n"
        "        criteria:\n"
        "          - 追问肿块持续时间和伴随症状\n"
        "        reference_answers:\n"
        "          - 先确认肿块出现多久、是否变大及有无疼痛。",
    ).replace(
        "        criterion: 建议尽快到乳腺专科就诊",
        "        criteria:\n"
        "          - 建议尽快到乳腺专科就诊\n"
        "        reference_answers:\n"
        "          - 建议今天联系乳腺专科完成评估。\n"
        "        deduction_rule: 遗漏该建议扣 1 分。",
    )
    created = upload(client, v21_yaml, name="v21-reference-answers")
    assert created.status_code == 201, created.text

    benchmark_id = created.json()["id"]
    content = client.get(f"/api/benchmarks/{benchmark_id}/cases/api_v2_001/content")
    assert content.status_code == 200, content.text
    case = content.json()["case"]
    assert case["schema_version"] == "2.1"
    assert case["evaluation"]["dimension_criteria"]["clinical_inquiry"]["reference_answers"] == ["先确认肿块出现多久、是否变大及有无疼痛。"]
    assert case["evaluation"]["guidelines"][0]["reference_answers"] == ["建议今天联系乳腺专科完成评估。"]


def test_upload_keeps_scripted_multiturn_context_and_mode_default(client) -> None:
    """旧格式脚本式多轮可导入；动态 conversation 的三轮限制不受影响。"""
    payload = yaml.safe_load(V2_YAML)
    payload[0]["turns"] = [
        {"role": "user", "content": f"第 {index} 轮用户追问"}
        for index in range(1, 19)
    ]
    response = client.post(
        "/api/benchmarks",
        data={
            "name": "scripted-multiturn",
            "source": "offline",
            "default_evaluation_mode": "multi_turn",
        },
        files={
            "file": (
                "cases.yaml",
                yaml.safe_dump(payload, allow_unicode=True).encode(),
                "application/x-yaml",
            )
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["default_evaluation_mode"] == "multi_turn"
    benchmark_id = response.json()["id"]
    cases = client.get(f"/api/benchmarks/{benchmark_id}/cases")
    assert cases.status_code == 200
    assert len(cases.json()) == 1


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
    assert profile == {
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
    assert profile["current_concern"] == "乳腺结节随访"
    agent_profile = case.initial_state.to_agent_payload()["user_profile"]
    assert agent_profile["current_concern"] == "breast_tumor"
    assert agent_profile["facts"]["当前关注"] == "乳腺结节随访"


def test_upload_accepts_free_profile_and_timeline_keys(client, settings) -> None:
    with_profile = V2_YAML.replace(
        "  turns:",
        "  initial_state:\n"
        "    user_profile:\n"
        "      年龄: 中年\n"
        "      性别: 女性\n"
        "      关注情况: 贫血\n"
        "    Timeline:\n"
        "      - 病历: 正在服用奥拉帕利\n"
        "        患者自定义标签: 需关注贫血\n"
        "  turns:",
    )
    response = upload(client, with_profile, name="localized-profile-and-memory")
    assert response.status_code == 201, response.text
    benchmark_id = response.json()["id"]
    with session_scope() as session:
        benchmark = session.get(Benchmark, benchmark_id)
        case = load_benchmark_cases(benchmark, settings=settings)[0]

    assert case.initial_state.user_profile["年龄"] == "中年"
    assert case.initial_state.user_profile["性别"] == "女性"
    assert case.initial_state.timeline[0]["患者自定义标签"] == "需关注贫血"
    agent_profile = case.initial_state.to_agent_payload()["user_profile"]
    assert agent_profile["facts"]["关注情况"] == "贫血"
    assert len(case.initial_state.to_agent_payload()["long_term_memories"]) == 2


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


def test_run_case_image_endpoint_uses_frozen_snapshot_after_benchmark_changes(client, settings) -> None:
    case_with_markdown_image = V2_YAML.replace(
        "      content: 乳房摸到硬块怎么办？",
        "      content: \"![报告图](images/case-snapshot-1.jpg)\"",
    )
    package = io.BytesIO()
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("cases.yaml", case_with_markdown_image)
        archive.writestr("images/case-snapshot-1.jpg", b"frozen-jpeg-content")
    uploaded = client.post(
        "/api/benchmarks",
        data={"name": "zip-snapshot-image-benchmark", "source": "offline"},
        files={"file": ("benchmark.zip", package.getvalue(), "application/zip")},
    )
    assert uploaded.status_code == 201, uploaded.text
    benchmark_id = uploaded.json()["id"]

    with session_scope() as session:
        benchmark = session.get(Benchmark, benchmark_id)
        cases = load_benchmark_cases(benchmark, settings=settings)
        run = EvalRun(run_slug="image_snapshot", name="图片快照", status="success", benchmark_id=benchmark_id)
        session.add(run)
        session.flush()
        snapshot_case_images(settings.outputs_dir / run.run_slug, cases, Path(benchmark.storage_path))
        (Path(benchmark.storage_path) / "images" / "case-snapshot-1.jpg").unlink()
        session.add(
            CaseResultRow(
                run_id=run.id,
                sample_id="api_v2_001",
                detail_json={
                    "case": {"turns": [{"role": "user", "content": "![报告图](images/case-snapshot-1.jpg)"}]},
                    "trace": {"messages": [{"role": "user", "content": "![报告图](images/case-snapshot-1.jpg)"}]},
                },
            )
        )
        run_id = run.id

    response = client.get(f"/api/runs/{run_id}/cases/api_v2_001/images/images/case-snapshot-1.jpg")
    assert response.status_code == 200, response.text
    assert response.content == b"frozen-jpeg-content"


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
    assert len(body["model_comparison"]["dimensions"]) == 8
    assert body["model_comparison"]["ttft_rule"].startswith("TTFT")
    assert {item["value"] for item in body["model_comparison"]["values"]} == {
        "1",
        "2",
        "tie",
        "na",
    }


def test_evaluation_accounts_endpoint(client) -> None:
    response = client.get("/api/config/evaluation-accounts")

    assert response.status_code == 200
    body = response.json()
    assert len(body["accounts"]) == 16
    assert body["accounts"][0]["pool_label"] == "普通评测"
    assert body["accounts"][8]["pool_label"] == "长期记忆评测"
