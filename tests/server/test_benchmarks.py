"""benchmark 库测试：合法上传、非法拒绝、builtin 注册、用例解析。"""

from __future__ import annotations

import yaml
import pytest

from server.benchmarks import (
    BenchmarkValidationError,
    _create_uploaded_benchmark_from_yaml_bytes,
    create_uploaded_benchmark,
    create_uploaded_benchmark_from_feishu_base,
    create_uploaded_benchmark_from_feishu_url,
    ensure_builtin_benchmark,
    export_benchmark_yaml,
    feishu_base_records_to_yaml_bytes,
    feishu_sheet_cells_to_yaml_bytes,
    load_benchmark_cases,
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


def _online_yaml_bytes(cases: list[dict]) -> bytes:
    return yaml.safe_dump(cases, allow_unicode=True, sort_keys=False).encode("utf-8")


def test_upload_online_file_rejected(session, settings):
    # 线上 benchmark 只能经飞书 Base URL 导入；文件上传（含旧 JSONL）一律拒绝。
    with pytest.raises(BenchmarkValidationError):
        create_uploaded_benchmark(
            session,
            name="线上文件",
            content='{"用户输入内容":"x","Cx输出内容":"y"}\n'.encode("utf-8"),
            filename="x.jsonl",
            source="online",
            settings=settings,
        )


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
    assert data[0]["sub_scenario"] == "能吃糖吗"
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

    data = yaml.safe_load(feishu_sheet_cells_to_yaml_bytes([sheet]).decode("utf-8"))

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


def test_feishu_sheet_cells_merge_text_and_image_columns_per_turn():
    sheet = {
        "sheet_id": "7bafeb",
        "sheet_name": "Sheet1",
        "row_indices": [1, 2],
        "cells": [
            [
                {"value": "序号"},
                {"value": "用户档案"},
                {"value": "第1轮用户输入"},
                {"value": "第1轮用户输入图片"},
                {"value": "第1轮Cx回复"},
                {"value": "第2轮用户输入"},
                {"value": "第2轮用户输入图片"},
                {"value": "第2轮Cx回复"},
            ],
            [
                {"value": "1"},
                {"value": "性别:女"},
                {"value": "这两份茶可以喝吗"},
                {
                    "rich_text": [
                        {
                            "type": "embed-image",
                            "image_token": "TeaImageToken",
                            "image_width": 800,
                            "image_height": 600,
                        }
                    ]
                },
                {"value": "第一答"},
                {"value": "普洱呢"},
                {"value": "这里误填了一段文字，不应该进入用户输入"},
                {"value": "第二答"},
            ],
        ],
    }

    data = yaml.safe_load(feishu_sheet_cells_to_yaml_bytes([sheet]).decode("utf-8"))

    assert data[0]["sample_id"] == "online_Sheet1_2"
    assert data[0]["sub_scenario"] == (
        "这两份茶可以喝吗 [图片：image_token=TeaImageToken，尺寸=800x600]"
    )
    assert data[0]["turns"] == [
        {
            "role": "user",
            "content": "这两份茶可以喝吗\n[图片：image_token=TeaImageToken，尺寸=800x600]",
        },
        {"role": "assistant", "content": "第一答"},
        {"role": "user", "content": "普洱呢"},
        {"role": "assistant", "content": "第二答"},
    ]


def test_feishu_sheet_cells_imports_new_text_and_image_split_tabs_with_profile():
    text_sheet = {
        "sheet_id": "0kRFoB",
        "sheet_name": "纯文字",
        "row_indices": [1, 2],
        "cells": [
            [
                {"value": "序号"},
                {"value": "用户档案"},
                {"value": "第1轮用户文字"},
                {"value": "第1轮cx输出"},
                {"value": "第2轮用户文字"},
                {"value": "第2轮cx输出"},
            ],
            [
                {"value": "1"},
                {"value": "女，32岁，内分泌治疗中"},
                {"value": "纯文字第一问"},
                {"value": "纯文字第一答"},
                {"value": "纯文字第二问"},
                {"value": "纯文字第二答"},
            ],
        ],
    }
    image_sheet = {
        "sheet_id": "ubK3kj",
        "sheet_name": "含图片",
        "row_indices": [1, 3],
        "cells": [
            [
                {"value": "用户档案"},
                {"value": "第一轮用户输入"},
                {"value": "第一轮Cx输出"},
                {"value": "第二轮用户输入"},
                {"value": "第二轮用户输入"},
                {"value": "第二轮用户输入"},
                {"value": "第二轮用户输入"},
                {"value": "第二轮Cx输出"},
            ],
            [
                {"value": "男，45岁，术后复查"},
                {"value": "第一轮文字"},
                {"value": "第一轮回答"},
                {"value": "第二轮补充文字"},
                {
                    "rich_text": [
                        {
                            "type": "embed-image",
                            "image_token": "ImageTokenA",
                            "image_width": 1000,
                            "image_height": 800,
                        }
                    ]
                },
                {
                    "rich_text": [
                        {
                            "type": "embed-image",
                            "image_token": "ImageTokenB",
                            "image_width": 600,
                            "image_height": 400,
                        }
                    ]
                },
                {"value": "第二轮另一段文字"},
                {"value": "第二轮回答"},
            ],
        ],
    }

    data = yaml.safe_load(
        feishu_sheet_cells_to_yaml_bytes([text_sheet, image_sheet]).decode("utf-8")
    )

    assert len(data) == 2
    assert data[0]["turns"] == [
        {"role": "user", "content": "纯文字第一问"},
        {"role": "assistant", "content": "纯文字第一答"},
        {"role": "user", "content": "纯文字第二问"},
        {"role": "assistant", "content": "纯文字第二答"},
    ]
    assert data[0]["sub_scenario"] == "纯文字第一问"
    assert data[1]["sub_scenario"] == "第一轮文字"
    assert data[0]["notes"] == "用户档案：\n女，32岁，内分泌治疗中"
    assert data[1]["turns"] == [
        {"role": "user", "content": "第一轮文字"},
        {"role": "assistant", "content": "第一轮回答"},
        {
            "role": "user",
            "content": (
                "第二轮补充文字\n"
                "[图片：image_token=ImageTokenA，尺寸=1000x800]\n"
                "[图片：image_token=ImageTokenB，尺寸=600x400]\n"
                "第二轮另一段文字"
            ),
        },
        {"role": "assistant", "content": "第二轮回答"},
    ]
    assert data[1]["notes"] == "用户档案：\n男，45岁，术后复查"


def test_feishu_sheet_cells_aggregate_multiple_tabs():
    def _tab(name: str, question: str) -> dict:
        return {
            "sheet_id": name,
            "sheet_name": name,
            "row_indices": [1, 2],
            "cells": [
                [{"value": "会话标题"}, {"value": "第一轮用户输入"}, {"value": "第一轮Cx输出"}],
                [{"value": f"{name}标题"}, {"value": question}, {"value": "答"}],
            ],
        }

    sheets = [_tab("day1", "问A"), _tab("day2", "问B")]
    data = yaml.safe_load(feishu_sheet_cells_to_yaml_bytes(sheets).decode("utf-8"))

    # 两张表各产出一条用例，sample_id 跨表唯一（tab 名进 sample_id 前缀）。
    assert len(data) == 2
    assert [c["sample_id"] for c in data] == ["online_day1_2", "online_day2_2"]
    assert data[0]["turns"][0]["content"] == "问A"
    assert data[1]["turns"][0]["content"] == "问B"


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
        return [
            {
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
        ]

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


def test_export_online_case_yaml_keeps_minimal_qa(session, settings):
    bm = _create_uploaded_benchmark_from_yaml_bytes(
        session,
        name="线上短用例",
        yaml_content=_online_yaml_bytes([
            {
                "sample_id": "online_28",
                "scenario": "线上真实对话",
                "sub_scenario": "内分泌治疗骨密度检查频率",
                "level": "L2",
                "score_profile": "default",
                "source": "online",
                "turns": [
                    {"role": "user", "content": "内分泌治疗期间骨密度检查一般多久做一次？"},
                    {"role": "assistant", "content": "骨密度检查频率主要看骨量基线情况和用药方案。"},
                ],
            }
        ]),
        filename="online.yaml",
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
    answer = "骨密度检查主要看骨量基线情况和用药方案。\n\n- 基线评估：开始时做一次\n- 常规随访：通常每 1-2 年复查一次"
    bm = _create_uploaded_benchmark_from_yaml_bytes(
        session,
        name="线上长回复",
        yaml_content=_online_yaml_bytes([
            {
                "sample_id": "online_28",
                "scenario": "线上真实对话",
                "sub_scenario": "内分泌治疗骨密度检查频率",
                "level": "L2",
                "score_profile": "default",
                "source": "online",
                "turns": [
                    {"role": "user", "content": "内分泌治疗期间骨密度检查一般多久做一次？"},
                    {"role": "assistant", "content": answer},
                ],
            }
        ]),
        filename="online.yaml",
        source="online",
        settings=settings,
    )
    session.commit()

    _, text = export_case_yaml(bm, "online_28", settings=settings)
    data = yaml.safe_load(text)

    assert "content: |" in text
    assert "content: '" not in text
    assert data[0]["turns"][1]["content"] == answer


def test_export_online_case_yaml_uses_block_notes_for_user_profile(session, settings):
    bm = _create_uploaded_benchmark_from_yaml_bytes(
        session,
        name="线上用户档案",
        yaml_content=_online_yaml_bytes([
            {
                "sample_id": "online_profile",
                "scenario": "线上真实对话",
                "sub_scenario": "第一问",
                "level": "L2",
                "score_profile": "default",
                "source": "online",
                "turns": [
                    {"role": "user", "content": "第一问"},
                    {"role": "assistant", "content": "第一答"},
                ],
                "notes": "用户档案：\n女，32岁\n用药：依西美坦",
            }
        ]),
        filename="online.yaml",
        source="online",
        settings=settings,
    )
    session.commit()

    _, text = export_case_yaml(bm, "online_profile", settings=settings)
    data = yaml.safe_load(text)

    assert "notes: |" in text
    assert data[0]["notes"] == "用户档案：\n女，32岁\n用药：依西美坦"


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
