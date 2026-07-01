"""benchmark 库测试：合法上传、非法拒绝、builtin 注册、用例解析。"""

from __future__ import annotations

import json

import yaml
import pytest

from server.benchmarks import (
    BenchmarkValidationError,
    create_uploaded_benchmark,
    create_uploaded_benchmark_from_feishu_base,
    create_uploaded_benchmark_from_feishu_url,
    ensure_builtin_benchmark,
    export_benchmark_yaml,
    feishu_base_records_to_yaml_bytes,
    feishu_sheet_cells_to_yaml_bytes,
    load_benchmark_cases,
    online_jsonl_to_yaml_bytes,
    overwrite_benchmark_from_yaml,
    export_case_yaml,
    replace_uploaded_benchmark,
)

VALID_YAML = """
- sample_id: up_001
  scenario: 症状
  level: L3
  score_profile: red_flag
  turns:
    - role: user
      content: 我胸口痛
- sample_id: up_002
  scenario: 筛查
  level: L1
  score_profile: knowledge
  turns:
    - role: user
      content: 多久做一次乳腺筛查
""".strip().encode("utf-8")

INVALID_YAML = """
- sample_id: bad_001
  scenario: 缺 level 和 turns 的非法用例
""".strip().encode("utf-8")


def test_upload_valid_benchmark(session, settings):
    bm = create_uploaded_benchmark(
        session, name="我的用例集", content=VALID_YAML, filename="mine.yaml", settings=settings
    )
    session.commit()
    assert bm.id is not None
    assert bm.source == "offline"
    assert bm.case_count == 2
    assert set(bm.tags) == {"red_flag", "knowledge"}
    assert set(bm.levels) == {"L1", "L3"}
    # 用例已落到 uploads/<id>/ 且可重新加载
    cases = load_benchmark_cases(bm, settings=settings)
    assert {c.sample_id for c in cases} == {"up_001", "up_002"}


NEW_YAML = (
    "- sample_id: rep_1\n  scenario: s\n  level: L2\n  turns:\n"
    "    - role: user\n      content: hi"
).encode("utf-8")


def test_export_and_replace_benchmark(session, settings):
    bm = create_uploaded_benchmark(
        session, name="原集", content=VALID_YAML, filename="orig.yaml", settings=settings
    )
    session.commit()

    # 下载导出：上传集返回原始内容
    fname, text = export_benchmark_yaml(bm, settings)
    assert "up_001" in text

    # 覆盖重传
    replace_uploaded_benchmark(session, bm, content=NEW_YAML, filename="new.yaml", settings=settings)
    session.commit()
    assert bm.case_count == 1
    assert bm.levels == ["L2"]
    cases = load_benchmark_cases(bm, settings=settings)
    assert {c.sample_id for c in cases} == {"rep_1"}


ONLINE_JSONL = (
    '{"序号":"28","会话标题":"内分泌治疗骨密度检查频率","对话链接":"https://cx.senzco.com/s/demo",'
    '"用户发送时间":"2026-06-29 06:25:24","Cx回复时间":"2026-06-29 06:25:35",'
    '"用户输入内容":"内分泌治疗期间骨密度检查一般多久做一次？",'
    '"Cx输出内容":"骨密度检查频率主要看骨量基线情况和用药方案。","是否点踩":"Y"}\n'
    '{"序号":"99","会话标题":"抗阻运动与瑜伽对比","用户输入内容":"抗阻运动好还是做瑜伽好",'
    '"Cx输出内容":"两种运动各有侧重，建议从轻量开始。","是否点踩":"N"}\n'
).encode("utf-8")


def test_online_jsonl_converts_to_qa_yaml():
    data = yaml.safe_load(online_jsonl_to_yaml_bytes(ONLINE_JSONL).decode("utf-8"))

    assert len(data) == 2
    assert data[0]["sample_id"] == "online_28"
    assert data[0]["source"] == "online"
    assert data[0]["turns"] == [
        {"role": "user", "content": "内分泌治疗期间骨密度检查一般多久做一次？"},
        {"role": "assistant", "content": "骨密度检查频率主要看骨量基线情况和用药方案。"},
    ]
    assert set(data[0]) == {
        "sample_id",
        "scenario",
        "sub_scenario",
        "level",
        "score_profile",
        "source",
        "turns",
    }


def test_online_jsonl_deduplicates_colliding_sample_ids():
    rows = [
        {"序号": "a!", "用户输入内容": "第一问", "Cx输出内容": "第一答"},
        {"序号": "a?", "用户输入内容": "第二问", "Cx输出内容": "第二答"},
        {"序号": "a_2", "用户输入内容": "第三问", "Cx输出内容": "第三答"},
    ]
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows).encode("utf-8")

    data = yaml.safe_load(online_jsonl_to_yaml_bytes(content).decode("utf-8"))

    assert [item["sample_id"] for item in data] == ["online_a", "online_a_2", "online_a_2_2"]


def test_feishu_base_records_convert_to_multiturn_online_yaml():
    records = [
        {
            "record_id": "rec_a",
            "fields": {
                "会话标题": "乳腺癌内分泌期能否吃糖",
                "第一轮用户输入": [{"type": "text", "text": "能吃糖吗"}],
                "第一轮Cx输出": "可以吃天然食物中的糖，控制添加糖。",
                "第二轮用户输入": "代糖呢",
                "第二轮Cx输出": "代糖可适量使用。",
                "第一轮用户输入(图片)": [
                    {"name": "配料表.png", "url": "https://example/ingredient.png"}
                ],
            },
        }
    ]

    data = yaml.safe_load(feishu_base_records_to_yaml_bytes(records).decode("utf-8"))

    assert data[0]["sample_id"] == "online_rec_a"
    assert data[0]["sub_scenario"] == "乳腺癌内分泌期能否吃糖"
    assert data[0]["source"] == "online"
    assert data[0]["turns"] == [
        {"role": "user", "content": "能吃糖吗"},
        {"role": "assistant", "content": "可以吃天然食物中的糖，控制添加糖。"},
        {"role": "user", "content": "代糖呢"},
        {"role": "assistant", "content": "代糖可适量使用。"},
    ]
    assert "配料表.png" in data[0]["notes"]


def test_feishu_base_records_deduplicates_colliding_sample_ids():
    records = [
        {"record_id": "rec/a", "fields": {"第一轮用户输入": "第一问"}},
        {"record_id": "rec?a", "fields": {"第一轮用户输入": "第二问"}},
        {"record_id": "rec_a_2", "fields": {"第一轮用户输入": "第三问"}},
    ]

    data = yaml.safe_load(feishu_base_records_to_yaml_bytes(records).decode("utf-8"))

    assert [item["sample_id"] for item in data] == [
        "online_rec_a",
        "online_rec_a_2",
        "online_rec_a_2_2",
    ]


def test_feishu_sheet_cells_convert_multiturn_images_to_online_yaml():
    sheet = {
        "sheet_id": "bdbf75",
        "sheet_name": "20260629",
        "row_indices": [1, 55],
        "cells": [
            [
                {"value": "会话标题"},
                {"value": "第一轮用户输入"},
                {"value": "第一轮Cx输出"},
                {"value": "第二轮用户输入"},
                {"value": "第二轮Cx输出"},
                {"value": "第五轮用户输入"},
                {"value": "第五轮Cx输出"},
            ],
            [
                {"value": "图片咨询"},
                {
                    "rich_text": [
                        {
                            "type": "embed-image",
                            "image_token": "NmGAbNRU0oGknQx0YFXcA4jfnjh",
                            "image_width": 1200,
                            "image_height": 1600,
                        }
                    ]
                },
                {"value": "第一答"},
                {
                    "rich_text": [
                        {
                            "type": "embed-image",
                            "image_token": "Rhb9bkUUfoA7rSxq4YzcVTT8nAs",
                            "image_width": 1200,
                            "image_height": 1600,
                        }
                    ]
                },
                {"value": "第二答"},
                {"value": "第五问"},
                {"value": "第五答"},
            ],
        ],
    }

    data = yaml.safe_load(feishu_sheet_cells_to_yaml_bytes(sheet).decode("utf-8"))

    assert data[0]["sample_id"] == "online_20260629_55"
    assert data[0]["source"] == "online"
    assert data[0]["turns"] == [
        {
            "role": "user",
            "content": "[图片：image_token=NmGAbNRU0oGknQx0YFXcA4jfnjh，尺寸=1200x1600]",
        },
        {"role": "assistant", "content": "第一答"},
        {
            "role": "user",
            "content": "[图片：image_token=Rhb9bkUUfoA7rSxq4YzcVTT8nAs，尺寸=1200x1600]",
        },
        {"role": "assistant", "content": "第二答"},
        {"role": "user", "content": "第五问"},
        {"role": "assistant", "content": "第五答"},
    ]
    assert "notes" not in data[0]


def test_upload_online_feishu_base_benchmark(session, settings, monkeypatch):
    from server import feishu_base

    def fake_fetch(access_token: str, source_url: str):
        assert access_token == "u-token"
        assert source_url == "https://example.feishu.cn/base/app?table=tbl"
        return [
            {
                "record_id": "rec_a",
                "fields": {
                    "会话标题": "多轮会话",
                    "第一轮用户输入": "第一问",
                    "第一轮Cx输出": "第一答",
                    "第二轮用户输入": "第二问",
                    "第二轮Cx输出": "第二答",
                },
            }
        ]

    monkeypatch.setattr(feishu_base, "fetch_base_records", fake_fetch)

    bm = create_uploaded_benchmark_from_feishu_base(
        session,
        name="飞书线上问题集",
        source_url="https://example.feishu.cn/base/app?table=tbl",
        access_token="u-token",
        settings=settings,
    )
    session.commit()

    assert bm.source == "online"
    cases = load_benchmark_cases(bm, settings=settings)
    assert cases[0].sample_id == "online_rec_a"
    assert [t.content for t in cases[0].turns] == ["第一问", "第一答", "第二问", "第二答"]


def test_upload_online_feishu_sheet_benchmark(session, settings, monkeypatch):
    from server import feishu_sheet

    def fake_fetch(access_token: str, source_url: str):
        assert access_token == "u-token"
        assert source_url == "https://example.feishu.cn/wiki/sht_token"
        return {
            "sheet_id": "bdbf75",
            "sheet_name": "20260629",
            "row_indices": [1, 9],
            "cells": [
                [{"value": "会话标题"}, {"value": "第一轮用户输入"}, {"value": "第一轮Cx输出"}],
                [
                    {"value": "图片咨询"},
                    {
                        "rich_text": [
                            {
                                "type": "embed-image",
                                "image_token": "RKuObri3Wob9j5x8Nk4cHEk1nOh",
                                "image_width": 739,
                                "image_height": 1600,
                            }
                        ]
                    },
                    {"value": "报告解读"},
                ],
            ],
        }

    monkeypatch.setattr(feishu_sheet, "fetch_sheet_cells", fake_fetch)

    bm = create_uploaded_benchmark_from_feishu_url(
        session,
        name="飞书 Sheet 线上问题集",
        source_url="https://example.feishu.cn/wiki/sht_token",
        access_token="u-token",
        settings=settings,
    )
    session.commit()

    assert bm.source == "online"
    cases = load_benchmark_cases(bm, settings=settings)
    assert cases[0].sample_id == "online_20260629_9"
    assert "image_token=RKuObri3Wob9j5x8Nk4cHEk1nOh" in cases[0].turns[0].content


def test_upload_online_jsonl_benchmark(session, settings):
    bm = create_uploaded_benchmark(
        session,
        name="线上问题集",
        content=ONLINE_JSONL,
        filename="20260629.jsonl",
        source="online",
        settings=settings,
    )
    session.commit()

    assert bm.source == "online"
    assert bm.case_count == 2
    cases = load_benchmark_cases(bm, settings=settings)
    assert [c.sample_id for c in cases] == ["online_28", "online_99"]
    assert cases[0].turns[0].role == "user"
    assert cases[0].turns[1].role == "assistant"


def test_export_online_case_yaml_keeps_minimal_qa(session, settings):
    bm = create_uploaded_benchmark(
        session,
        name="线上短用例",
        content=ONLINE_JSONL,
        filename="20260629.jsonl",
        source="online",
        settings=settings,
    )
    session.commit()

    _, text = export_case_yaml(bm, "online_28", settings=settings)
    data = yaml.safe_load(text)

    assert len(data) == 1
    assert set(data[0]) == {
        "sample_id",
        "scenario",
        "sub_scenario",
        "level",
        "score_profile",
        "source",
        "turns",
    }


def test_export_online_case_yaml_uses_block_content_for_multiline(session, settings):
    row = {
        "序号": "28",
        "会话标题": "内分泌治疗骨密度检查频率",
        "用户输入内容": "内分泌治疗期间骨密度检查一般多久做一次？",
        "Cx输出内容": "骨密度检查主要看骨量基线情况和用药方案。\n\n- 基线评估：开始时做一次\n- 常规随访：通常每 1-2 年复查一次",
    }
    bm = create_uploaded_benchmark(
        session,
        name="线上长回复",
        content=(json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8"),
        filename="20260629.jsonl",
        source="online",
        settings=settings,
    )
    session.commit()

    _, text = export_case_yaml(bm, "online_28", settings=settings)
    data = yaml.safe_load(text)

    assert "content: |" in text
    assert "content: '" not in text
    assert data[0]["turns"][1]["content"] == row["Cx输出内容"]


def test_replace_builtin_rejected(session, settings):
    bm = ensure_builtin_benchmark(session, settings)
    session.commit()
    with pytest.raises(BenchmarkValidationError):
        replace_uploaded_benchmark(session, bm, content=NEW_YAML, settings=settings)


def test_duplicate_name_rejected(session, settings):
    create_uploaded_benchmark(session, name="重名集", content=VALID_YAML, settings=settings)
    session.commit()
    with pytest.raises(BenchmarkValidationError):
        create_uploaded_benchmark(session, name="重名集", content=VALID_YAML, settings=settings)


def test_upload_invalid_benchmark_rejected(session, settings):
    with pytest.raises(BenchmarkValidationError):
        create_uploaded_benchmark(
            session, name="坏的", content=INVALID_YAML, settings=settings
        )


def test_upload_non_utf8_rejected(session, settings):
    with pytest.raises(BenchmarkValidationError):
        create_uploaded_benchmark(
            session, name="二进制", content=b"\xff\xfe\x00bad", settings=settings
        )


# 覆盖保存：仅编辑 up_001 判据，YAML 只含 up_001（模拟过滤子集编辑）
OVERWRITE_YAML = (
    "- sample_id: up_001\n"
    "  expected_behavior:\n"
    "    must_have:\n"
    "      - keyword: 新要点\n"
)


def test_overwrite_yaml_updates_in_place(session, settings):
    bm = create_uploaded_benchmark(
        session, name="待覆盖集", content=VALID_YAML, filename="o.yaml", settings=settings
    )
    session.commit()
    bid = bm.id

    overwrite_benchmark_from_yaml(session, bm, yaml_text=OVERWRITE_YAML, settings=settings)
    session.commit()

    # 同一 benchmark（id 不变）、未编辑的 up_002 原样保留、总数不变
    assert bm.id == bid
    assert bm.source == "offline"
    cases = {c.sample_id: c for c in load_benchmark_cases(bm, settings=settings)}
    assert set(cases) == {"up_001", "up_002"}
    # up_001 判据被更新
    kws = [p.keyword for p in cases["up_001"].expected_behavior.must_have]
    assert "新要点" in kws


def test_overwrite_yaml_builtin_rejected(session, settings):
    bm = ensure_builtin_benchmark(session, settings)
    session.commit()
    with pytest.raises(BenchmarkValidationError):
        overwrite_benchmark_from_yaml(session, bm, yaml_text=OVERWRITE_YAML, settings=settings)


def test_overwrite_yaml_zero_match_rejected(session, settings):
    bm = create_uploaded_benchmark(
        session, name="零匹配集", content=VALID_YAML, filename="z.yaml", settings=settings
    )
    session.commit()
    bad = "- sample_id: not_exist\n  expected_behavior:\n    must_have:\n      - keyword: x\n"
    with pytest.raises(BenchmarkValidationError):
        overwrite_benchmark_from_yaml(session, bm, yaml_text=bad, settings=settings)


def test_ensure_builtin_idempotent(session, settings):
    first = ensure_builtin_benchmark(session, settings)
    session.commit()
    assert first is not None
    assert first.source == "builtin"
    assert first.case_count > 0
    # 再次调用不重复创建
    second = ensure_builtin_benchmark(session, settings)
    assert second.id == first.id


def test_ensure_builtin_refreshes_case_count(session, settings):
    bm = ensure_builtin_benchmark(session, settings)
    assert bm is not None
    bm.case_count = 71
    session.flush()
    refreshed = ensure_builtin_benchmark(session, settings)
    cases = load_benchmark_cases(bm, settings=settings)
    assert refreshed.case_count == len(cases)
    assert refreshed.case_count != 71
