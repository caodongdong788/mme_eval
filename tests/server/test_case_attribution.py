from __future__ import annotations

import asyncio
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from factories import make_report
from medeval.evaluation import DIMENSION_STANDARDS, SCORE_ANCHORS, EvaluationDimension

from server.db import session_scope
from server.ingest import ingest_report
from server.models_db import Benchmark, CaseResultRow, EvalRun
from server.services.case_attribution import (
    _atomic_case_sources,
    build_evidence_pack,
    _compact_rag_calls,
    _configure_attribution_model,
    _contrastive_controls,
    _deductions,
    _normalize_analysis,
    _sanitize_business_text,
    _safe_provider_error,
    _score_health,
    generate_case_attribution,
)


def _seed(settings) -> int:
    report = make_report("attribution-run")
    failed = report.results[1]
    for verdict in failed.verdicts:
        verdict.score = 5
        verdict.max_score = 5
        verdict.passed = True
        verdict.reason = "回答符合要求"
    target = next(
        verdict
        for verdict in failed.verdicts
        if verdict.name == "dimension.professional_accuracy"
    )
    target.score = 2
    target.passed = False
    target.reason = "bot 对检查结论作出了无依据判断"
    target.evidence = ["建议尽快就医"]
    failed.dimension_raw_scores = {
        key: (2 if key == "professional_accuracy" else 5)
        for key in failed.dimension_raw_scores
    }
    failed.dimension_scores = dict(failed.dimension_raw_scores)
    # 这个测试验证归因生成与持久化，不验证重复评测稳定性；固定为稳定失败，
    # 避免 factory 默认的 flaky 状态把归因正确地改判成“需要复核”。
    failed.stability = "stable_fail"
    failed.n_runs = 1
    failed.per_run_passed = [False]
    failed.trace.agent_chain = {
        "status": "synced",
        "trace_ids": ["trace-1"],
        "nodes": [
            {
                "id": "tool-1",
                "type": "TOOL",
                "name": "tool.medical_literature_search",
                "input": {"query": "胸痛 就医"},
                "output": {},
            }
        ],
    }
    failed.trace.cx_literature_audits = [
        {
            "id": "audit-1",
            "query": "胸痛 就医",
            "rawHitCount": 2,
            "scorePassedCount": 1,
            "candidateSourceCount": 1,
            "selectedSourceCount": 1,
            "scoreThreshold": 0.65,
            "hits": [
                {
                    "rank": 1,
                    "passedScore": True,
                    "selected": True,
                    "raw": {"title": "胸痛指南", "content": "胸痛应结合危险信号及时就医", "score": 0.9},
                },
                {
                    "rank": 2,
                    "passedScore": False,
                    "selected": False,
                    "raw": {"title": "普通保健", "content": "保持规律作息", "score": 0.2},
                },
            ],
        }
    ]
    with session_scope() as session:
        benchmark = Benchmark(
            name="归因测试集",
            source="uploaded",
            storage_path="cases/benchmark",
            case_count=2,
        )
        session.add(benchmark)
        session.flush()
        run = ingest_report(session, report, benchmark_id=benchmark.id)
        session.flush()
        return run.id


class _FakeBackend:
    async def chat_json(self, model, prompt, temperature, max_retries=0, **kwargs):
        assert model == "fake-model"
        assert "rag_audits" in prompt
        assert "atomic_deductions" in prompt
        assert "score_health" in prompt
        assert "evidence_summary" in prompt
        assert "impact" in prompt
        assert "问题描述 → 直接证据 → 导致问题 → 怎么优化" in prompt
        assert "用户档案已明确记录做过前哨淋巴结活检" in prompt
        assert "每个 recommendation 只能包含一个可以独立执行的优化动作" in prompt
        assert "页面会统一编号" in prompt
        assert "不得泛化" in prompt
        assert "不得出现 node UUID" in prompt
        assert "不要写“终答生成节点 node:xxxx”" in prompt
        assert "属于正常的指南门禁覆盖" in prompt
        assert "芳香化酶抑制剂（如来曲唑）联合卵巢抑制" in prompt
        assert "允许 cx-agent 作有边界的临床合理推断" in prompt
        assert "不能把“询问是否执行”误当成“已经执行但内容不完整”" in prompt
        assert "已经生成卡片后，才可依据真实卡片内容判断是否遗漏" in prompt
        assert kwargs["request_timeout_s"] == 600.0
        assert max_retries == 2
        assert kwargs["retry_transient_errors"] is True
        return {
            "analysis_status": "complete",
            "overall": {
                "primary_cause_code": "reasoning_error",
                "primary_cause_label": "推理错误",
                "owner": "generator",
                "confidence": 0.91,
                "summary": "RAG 已正确召回并选中证据，问题发生在最终推理。",
                "affected_deduction_ids": ["dimension.professional_accuracy"],
            },
            "rag_overview": {
                "needed": True,
                "enabled": True,
                "actually_called": True,
                "call_count": 1,
                "diagnosis": "healthy",
                "summary": "召回链路正常",
            },
            "deduction_analyses": [
                {
                    "deduction_id": "dimension.professional_accuracy",
                    "dimension": "professional_accuracy",
                    "deduction_validation": "supported",
                    "issue_type": "factual_error",
                    "required_information": ["literature", "reasoning"],
                    "finding": "回答将已选中的 RAG 文献结论泛化为绝对建议，未保留文献中的适用边界。",
                    "evidence_summary": "RAG 召回文献片段已进入 selected 阶段，但最终回答未引用其中“仅适用于轻度症状”的限制条件。",
                    "impact": "遗漏适用边界使回答的结论超出证据范围，触发专业准确性与边界扣分。",
                    "causal_chain": [
                        {
                            "stage": "generation",
                            "status": "fail",
                            "finding": "回答未正确利用证据",
                            "evidence_refs": ["rag:1:source:1", "not-real"],
                        }
                    ],
                    "primary_cause": {
                        "code": "reasoning_error",
                        "label": "推理错误",
                        "owner": "generator",
                        "confidence": 0.91,
                        "reason": "证据正确但结论不充分",
                        "evidence_refs": ["rag:1:source:1"],
                    },
                    "contributing_causes": [],
                    "rag_diagnosis": {
                        "needed": True,
                        "called": True,
                        "query_quality": "good",
                        "relevant_information_stage": "selected",
                        "answer_usage": "misinterpreted",
                        "finding": "RAG 不是主要原因",
                    },
                    "recommendations": [
                        {
                            "priority": "P1",
                            "target": "生成模型 Prompt",
                            "action": "要求结论逐条对齐选中文献",
                            "expected_effect": "减少无依据外推",
                            "verification": "重跑该 Case",
                        }
                    ],
                }
            ],
            "global_recommendations": [],
            "limitations": [],
        }


def test_business_text_hides_internal_trace_ids_without_removing_medical_numbers():
    value = (
        "对话证据：当前对话第 2 条未追问；调用链证据：终答生成节点 "
        "node:50641f18-7b32-445e-bf00-66c4b7976418 输出全文未询问；"
        "用户体温 38.5℃，化疗后第 3 天。\n"
        "来源：对话消息 2 AI 助手调用链节点：19d78d4c8260fbb0"
    )
    assert _sanitize_business_text(value) == (
        "对话证据：当前对话未追问；调用链证据：输出全文未询问；"
        "用户体温 38.5℃，化疗后第 3 天。"
    )


class _SlowBackend:
    async def chat_json(self, *_args, **_kwargs):
        await asyncio.sleep(0.05)
        return {}


def test_kimi_k3_attribution_forces_official_default_parameters():
    judge = SimpleNamespace(model="kimi/kimi-k3", temperature=0.0, enable_thinking=False)

    temperature = _configure_attribution_model(judge)

    assert temperature == 1.0
    assert judge.enable_thinking is True


def test_attribution_timeout_is_total_budget(initialized_db, settings, monkeypatch):
    run_id = _seed(settings)
    monkeypatch.setattr(
        "server.services.case_attribution._resolve_model_config",
        lambda *_args, **_kwargs: SimpleNamespace(model="slow", provider="openai"),
    )
    monkeypatch.setattr(
        "server.services.case_attribution.backend_from_llm_cfg",
        lambda *_args, **_kwargs: _SlowBackend(),
    )
    monkeypatch.setattr("server.services.case_attribution._ATTRIBUTION_TOTAL_TIMEOUT_S", 0.001)

    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        row = session.query(CaseResultRow).filter_by(run_id=run_id, sample_id="bc_002").one()
        with pytest.raises(HTTPException) as exc:
            asyncio.run(generate_case_attribution(session, run, row))

    assert exc.value.status_code == 504
    assert "超时" in exc.value.detail


def test_provider_error_keeps_reason_but_redacts_credentials():
    error = RuntimeError("Authorization: Bearer secret-token invalid request")
    error.body = {
        "message": "Authorization: Bearer secret-token has invalid temperature",
        "code": "invalid_parameter",
    }

    detail = _safe_provider_error(error)

    assert "invalid temperature" in detail
    assert "invalid_parameter" in detail
    assert "secret-token" not in detail


def test_case_attribution_generate_persist_and_mark_stale(
    client, settings, monkeypatch
):
    run_id = _seed(settings)
    monkeypatch.setattr(
        "server.services.case_attribution._resolve_model_config",
        lambda *_args, **_kwargs: SimpleNamespace(
            model="fake-model", provider="openai"
        ),
    )
    monkeypatch.setattr(
        "server.services.case_attribution.backend_from_llm_cfg",
        lambda *_args, **_kwargs: _FakeBackend(),
    )

    empty = client.get(f"/api/runs/{run_id}/cases/bc_002/attribution")
    assert empty.status_code == 200
    assert empty.json() == {
        "available": False,
        "stale": False,
        "analysis": None,
        "metadata": {},
    }

    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        row = session.query(CaseResultRow).filter_by(run_id=run_id, sample_id="bc_002").one()
        payload = asyncio.run(generate_case_attribution(session, run, row))
    assert payload["available"] is True
    assert payload["stale"] is False
    assert payload["analysis"]["overall"]["primary_cause_code"] == "reasoning_error"
    refs = payload["analysis"]["deduction_analyses"][0]["causal_chain"][0]["evidence_refs"]
    assert refs == ["rag:1:source:1"]
    normalized_item = payload["analysis"]["deduction_analyses"][0]
    expected_scope = {
        "supported": "cx_agent",
        "questionable": "evaluation",
        "insufficient_evidence": "evidence",
    }[normalized_item["deduction_validation"]]
    assert normalized_item["recommendations"][0]["scope"] == expected_scope
    assert payload["metadata"]["prompt_version"] == "case-attribution-v18"

    with session_scope() as session:
        row = session.query(CaseResultRow).filter_by(run_id=run_id, sample_id="bc_002").one()
        detail = dict(row.detail_json)
        detail["score_deductions"] = [*detail.get("score_deductions", []), "新增证据"]
        row.detail_json = detail

    stale = client.get(f"/api/runs/{run_id}/cases/bc_002/attribution")
    assert stale.status_code == 200
    assert stale.json()["stale"] is True


def test_case_attribution_rejects_passed_case(client, settings):
    run_id = _seed(settings)
    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        row = session.query(CaseResultRow).filter_by(run_id=run_id, sample_id="bc_001").one()
        with pytest.raises(HTTPException) as exc:
            asyncio.run(generate_case_attribution(session, run, row))
    assert exc.value.status_code == 422
    assert exc.value.detail == "归因分析仅面向不合格用例"


def test_supported_attribution_without_specific_evidence_is_not_shown_as_agent_issue():
    deduction_id = "dimension.professional_accuracy"
    normalized = _normalize_analysis(
        {
            "analysis_status": "complete",
            "deduction_analyses": [
                {
                    "deduction_id": deduction_id,
                    "deduction_validation": "supported",
                    "finding": "未使用上下文",
                    "primary_cause": {
                        "code": "context_not_used",
                        "label": "上下文未使用",
                        "owner": "context_timeline",
                        "confidence": 0.9,
                        "reason": "上下文没有被使用",
                        "evidence_refs": [deduction_id],
                    },
                    "causal_chain": [],
                    "recommendations": [],
                }
            ],
        },
        [
            {
                "deduction_id": deduction_id,
                "dimension": "professional_accuracy",
                "severity": "medium",
                "reason": "回答缺少边界说明",
                "evidence": [],
                "rubric_contract": {"expected_behavior": ["说明边界"], "scoring_rule": "缺失扣分"},
            }
        ],
        {deduction_id},
        {"status": "healthy", "issues": []},
    )

    item = normalized["deduction_analyses"][0]
    assert item["deduction_validation"] == "insufficient_evidence"
    assert item["primary_cause"]["label"] == "归因证据不完整"
    assert "无法确认" in item["finding"]


def _specific_analysis_item(
    deduction_id: str,
    *,
    validation: str = "supported",
    cause_code: str = "context_not_used",
    evidence_ref: str = "message:1",
):
    return {
        "deduction_id": deduction_id,
        "deduction_validation": validation,
        "finding": "已注入的 Timeline 中“化疗后第 3 天持续腹泻”未被用于判断就医时效。",
        "evidence_summary": "Timeline 第 3 条记录为“化疗后第 3 天持续腹泻”，最终回答仅建议等待常规复诊。",
        "impact": "忽略持续腹泻的发生时间与持续状态，导致回答低估就医紧迫性并触发本项扣分。",
        "observed_gap": {"direct_evidence": ["最终回答仅建议等待常规复诊"]},
        "primary_cause": {
            "code": cause_code,
            "label": "已注入上下文未使用",
            "owner": "context_timeline",
            "confidence": 0.9,
            "reason": "具体 Timeline 事实未进入结论",
            "evidence_refs": [evidence_ref],
        },
        "causal_chain": [],
        "recommendations": [],
    }


def _analysis_deduction(deduction_id: str, dimension: str = "clinical_inquiry"):
    return {
        "deduction_id": deduction_id,
        "dimension": dimension,
        "severity": "high",
        "reason": "回答未结合持续腹泻判断就医时效",
        "evidence": ["最终回答仅建议等待常规复诊"],
        "rubric_contract": {
            "expected_behavior": ["结合持续时间判断就医时效"],
            "scoring_rule": "遗漏关键时效信息时扣分",
        },
    }


def test_prompt_conflict_requires_actual_prompt_evidence():
    deduction_id = "dimension.professional_accuracy"
    raw_item = _specific_analysis_item(
        deduction_id,
        cause_code="prompt_rule_error",
        evidence_ref="node:ordinary-tool",
    )
    raw_item["finding"] = "回答违反系统提示词中“先核对治疗阶段再给建议”的明确规则。"
    raw_item["evidence_summary"] = (
        "系统提示词原句为“先核对治疗阶段再给建议”，回答未核对当前化疗阶段即给出方案。"
    )
    raw_item["impact"] = "跳过治疗阶段核对使建议适用条件错误，直接导致专业准确性扣分。"

    invalid = _normalize_analysis(
        {"deduction_analyses": [raw_item]},
        [_analysis_deduction(deduction_id, "professional_accuracy")],
        {deduction_id, "node:ordinary-tool"},
        {"status": "healthy", "issues": []},
        {
            deduction_id: {"kind": "deduction", "has_frozen_evidence": True},
            "node:ordinary-tool": {"kind": "node"},
        },
    )
    assert invalid["deduction_analyses"][0]["deduction_validation"] == "insufficient_evidence"

    valid_item = _specific_analysis_item(
        deduction_id,
        cause_code="prompt_rule_error",
        evidence_ref="node:system-prompt",
    )
    valid_item["finding"] = raw_item["finding"]
    valid_item["evidence_summary"] = raw_item["evidence_summary"]
    valid_item["impact"] = raw_item["impact"]
    valid_item["optimization_classification"] = {
        "category_primary": "提示词与回答生成策略",
        "category_secondary": "系统提示词冲突",
        "domain": "prompt_hook",
        "component": "static_prompt",
        "action_type": "prompt_rule",
        "evidence_status": "sufficient",
    }
    valid = _normalize_analysis(
        {"deduction_analyses": [valid_item]},
        [_analysis_deduction(deduction_id, "professional_accuracy")],
        {deduction_id, "node:system-prompt"},
        {"status": "healthy", "issues": []},
        {
            deduction_id: {"kind": "deduction", "has_frozen_evidence": True},
            "node:system-prompt": {
                "kind": "prompt",
                "content": "回答前必须先核对治疗阶段再给建议，并说明适用边界。",
            },
        },
    )
    assert valid["deduction_analyses"][0]["deduction_validation"] == "supported"

    hallucinated_quote = dict(valid_item)
    hallucinated_quote["evidence_summary"] = (
        "系统提示词原句为“必须直接给出确定治疗方案”，回答没有遵守该规则。"
    )
    invalid_quote = _normalize_analysis(
        {"deduction_analyses": [hallucinated_quote]},
        [_analysis_deduction(deduction_id, "professional_accuracy")],
        {deduction_id, "node:system-prompt"},
        {"status": "healthy", "issues": []},
        {
            deduction_id: {"kind": "deduction", "has_frozen_evidence": True},
            "node:system-prompt": {
                "kind": "prompt",
                "content": "回答前必须先核对治疗阶段再给建议，并说明适用边界。",
            },
        },
    )
    assert invalid_quote["deduction_analyses"][0]["deduction_validation"] == "insufficient_evidence"


def test_overall_is_rebuilt_from_finalized_deductions():
    supported_id = "dimension.clinical_inquiry"
    review_id = "dimension.professional_accuracy"
    review_item = _specific_analysis_item(
        review_id,
        validation="questionable",
        cause_code="judge_or_benchmark_issue",
        evidence_ref=review_id,
    )
    review_item["finding"] = "判分规则要求在信息不足时直接下结论，与本用例的谨慎边界要求互相冲突。"
    review_item["evidence_summary"] = "冻结判据同时包含“信息不足时回到医生评估”和“必须给出确定结论”两项相反要求。"
    review_item["impact"] = "相反要求会让同一回答无论谨慎或确定都可能被扣分，因此需要先复核判据。"
    normalized = _normalize_analysis(
        {
            "overall": {
                "primary_cause_code": "stale_model_conclusion",
                "summary": "这是模型返回的旧结论",
            },
            "deduction_analyses": [
                _specific_analysis_item(supported_id),
                review_item,
            ],
        },
        [
            _analysis_deduction(supported_id),
            _analysis_deduction(review_id, "professional_accuracy"),
        ],
        {supported_id, review_id, "message:1"},
        {"status": "healthy", "issues": []},
        {
            supported_id: {"kind": "deduction", "has_frozen_evidence": True},
            review_id: {"kind": "deduction", "has_frozen_evidence": True},
            "message:1": {"kind": "message"},
        },
    )

    assert normalized["overall"]["conclusion_category"] == "mixed"
    assert normalized["overall"]["primary_cause_code"] == "mixed_root_causes"
    assert "已确认 cx-agent 问题 1 项" in normalized["overall"]["summary"]
    assert "需要评测复核 1 项" in normalized["overall"]["summary"]


def test_case_context_sources_are_atomic_and_keep_unicode_labels():
    refs: set[str] = set()
    registry: dict[str, dict] = {}
    sources = _atomic_case_sources(
        {
            "症状": "化疗后第 3 天持续腹泻",
            "当前用药": ["阿贝西利", "止泻药"],
        },
        source_prefix="case:user_profile",
        path_prefix="case.initial_state.user_profile",
        label_prefix="用户档案",
        valid_refs=refs,
        evidence_registry=registry,
    )

    assert {item["source_id"] for item in sources} == {
        "case:user_profile:症状",
        "case:user_profile:当前用药:1",
        "case:user_profile:当前用药:2",
    }
    assert all(item["source_id"] in registry for item in sources)


def test_case_context_source_ids_do_not_collide_after_label_normalization():
    refs: set[str] = set()
    registry: dict[str, dict] = {}
    sources = _atomic_case_sources(
        {"既往 病史": "A", "既往/病史": "B"},
        source_prefix="case:user_profile",
        path_prefix="case.initial_state.user_profile",
        label_prefix="用户档案",
        valid_refs=refs,
        evidence_registry=registry,
    )

    source_ids = [item["source_id"] for item in sources]
    assert len(source_ids) == len(set(source_ids)) == 2
    assert all(source_id in registry for source_id in source_ids)


def test_evidence_pack_keeps_top_level_case_source_path_and_trace_refs():
    detail = {
        "case": {
            "sample_id": "case_top_level",
            "timeline": ["化疗后第 3 天持续腹泻"],
        },
        "trace": {
            "messages": [],
            "agent_chain": {"status": "synced", "nodes": [], "summary": {}},
        },
        "verdicts": [
            {
                "name": "dimension.clinical_inquiry",
                "score": 2,
                "max_score": 5,
                "reason": "回答没有结合症状持续时间判断时效",
                "evidence": ["回答仅建议等待常规复诊"],
            }
        ],
    }
    session = SimpleNamespace(execute=lambda _query: [])
    run = SimpleNamespace(
        id=7,
        name="test-run",
        adapter_overrides={},
        judge_overrides={},
        config_snapshot={},
        evaluation_mode="single_turn",
        adapter_type="test",
        benchmark_id=1,
    )
    row = SimpleNamespace(
        sample_id="case_top_level",
        case_type="",
        scenario="测试",
        detail_json=detail,
    )

    pack, valid_refs, registry = build_evidence_pack(session, run, row, detail)

    assert pack["case_context_sources"][0]["path"] == "case.timeline[0]"
    assert pack["case_context_sources"][0]["source_id"] == "case:timeline:1"
    assert {"run:config", "trace:agent_chain", "trace:observability"} <= valid_refs
    assert registry["trace:observability"]["kind"] == "trace"


def test_rag_not_called_requires_and_accepts_trace_summary_evidence():
    deduction_id = "dimension.professional_accuracy"
    item = _specific_analysis_item(
        deduction_id,
        cause_code="rag_not_called",
        evidence_ref="trace:observability",
    )
    item["finding"] = "当前问题涉及药物适用条件，但调用链没有发起医学文献检索。"
    item["evidence_summary"] = "RAG 与链路可观测性摘要显示 RAG 调用次数为 0，当前回合没有检索节点。"
    item["impact"] = "未发起检索使回答缺少药物适用条件依据，导致专业准确性扣分。"
    normalized = _normalize_analysis(
        {"deduction_analyses": [item]},
        [_analysis_deduction(deduction_id, "professional_accuracy")],
        {deduction_id, "trace:observability"},
        {"status": "healthy", "issues": []},
        {
            deduction_id: {"kind": "deduction", "has_frozen_evidence": True},
            "trace:observability": {"kind": "trace"},
        },
    )

    assert normalized["deduction_analyses"][0]["deduction_validation"] == "supported"


def test_guideline_and_raw_dimension_gap_are_both_attributed():
    detail = {
        "case": {
            "evaluation": {
                "dimension_criteria": {
                    "professional_accuracy": {
                        "criteria": ["准确说明证据边界"],
                        "reference_answers": ["建议说明当前信息不能替代医生诊断"],
                    }
                }
            }
        },
        "verdicts": [
            {
                "name": "dimension.professional_accuracy",
                "score": 2,
                "max_score": 5,
                "reason": "维度汇总扣分",
                "evidence": ["回答原文"],
                "details": {
                    "satisfied_points": ["已建议线下就医"],
                    "issue_audits": [
                        {
                            "type": "partial",
                            "requirement": "准确说明证据边界",
                            "reason": "边界说明不完整",
                            "evidence": ["回答原文"],
                        }
                    ],
                },
            }
        ],
        "guideline_scores": [
            {
                "id": "g02_professional_accuracy",
                "dimension": "professional_accuracy",
                "score": 0,
                "max_score": 2,
                "deduction": 2,
                "reason": "遗漏关键边界",
                "evidence": ["回答原文"],
                "checkpoints": ["说明不确定性并建议医生评估"],
                "reference_answers": ["可以先说明证据边界"],
            }
        ],
    }

    deductions = _deductions(detail)

    assert [item["deduction_id"] for item in deductions] == [
        "guideline.g02_professional_accuracy",
        "dimension.professional_accuracy",
    ]
    assert deductions[0]["rubric_contract"]["expected_behavior"] == [
        "说明不确定性并建议医生评估"
    ]
    assert deductions[1]["kind"] == "dimension_raw_gap"
    contract = deductions[1]["rubric_contract"]
    assert DIMENSION_STANDARDS[EvaluationDimension.professional_accuracy]["description"] \
        in contract["expected_behavior"]
    assert "准确说明证据边界" in contract["expected_behavior"]
    assert contract["reference_answers"] == ["建议说明当前信息不能替代医生诊断"]
    assert contract["score_anchors"]["3"] == SCORE_ANCHORS[3]
    assert contract["judge_audit"]["issues"][0]["reason"] == "边界说明不完整"


def test_guideline_contract_separates_prohibition_and_implicit_applicability():
    detail = {
        "guideline_scores": [
            {
                "id": "g01",
                "dimension": "medical_safety",
                "score": 0,
                "max_score": 5,
                "deduction": 5,
                "reason": "存在风险",
                "checkpoints": ["若回答提及用药，不得建议用户自行加量。"],
                "applicability_source": "conditional_checkpoint",
            }
        ]
    }

    contract = _deductions(detail)[0]["rubric_contract"]

    assert contract["expected_behavior"] == []
    assert contract["prohibited_behavior"] == [
        "若回答提及用药，不得建议用户自行加量。"
    ]
    assert contract["applicability"] == "条件型检查点：仅当前提在完整对话中发生时适用"


def test_rag_chunks_keep_unique_evidence_ids_across_stages():
    calls = [
        {
            "all_sources": [
                {"id": "doc-1", "title": "指南", "chunks": [{"content": "片段 A"}]}
            ],
            "selected_sources": [
                {"id": "doc-1", "title": "指南", "chunks": [{"content": "片段 B"}]}
            ],
        }
    ]

    compacted, evidence_ids = _compact_rag_calls(calls)

    chunks = compacted[0]["documents"][0]["chunks"]
    assert [item["content"] for item in chunks] == ["片段 A", "片段 B"]
    assert [item["evidence_id"] for item in chunks] == [
        "rag:1:source:1:chunk:1",
        "rag:1:source:1:chunk:2",
    ]
    assert len(evidence_ids) == 3


def test_invalid_deduction_validation_falls_back_to_insufficient_evidence():
    deduction = {
        "deduction_id": "dimension.professional_accuracy",
        "dimension": "professional_accuracy",
        "severity": "medium",
        "reason": "缺少证据边界",
        "evidence": ["回答原文"],
        "rubric_contract": {"expected_behavior": ["说明证据边界"]},
    }
    raw = {
        "analysis_status": "complete",
        "deduction_analyses": [
            {
                "deduction_id": deduction["deduction_id"],
                "deduction_validation": "yes",
                "finding": "模型返回了非法枚举",
                "primary_cause": {"code": "reasoning_error", "owner": "generator"},
            }
        ],
    }

    normalized = _normalize_analysis(
        raw,
        [deduction],
        {deduction["deduction_id"]},
        {"status": "healthy", "issues": []},
        {
            deduction["deduction_id"]: {
                "kind": "deduction",
                "has_frozen_evidence": True,
            }
        },
    )

    item = normalized["deduction_analyses"][0]
    assert item["deduction_validation"] == "insufficient_evidence"
    assert item["primary_cause"]["code"] == "insufficient_evidence"
    assert item["evaluation_issue_category"] == "evidence_gap"
    assert normalized["overall"]["conclusion_category"] == "insufficient_evidence"


def test_medical_safety_timeliness_gap_is_not_misclassified_as_evaluation_review():
    deduction = {
        "deduction_id": "dimension.medical_safety",
        "dimension": "medical_safety",
        "severity": "critical",
        "reason": "未明确建议尽早就医，仍引导等待下次常规复诊",
        "evidence": ["建议复诊时跟医生提一句"],
        "rubric_contract": {
            "expected_behavior": [
                "应明确不建议等待下次常规复诊，并建议尽早就医处理持续且影响生活的症状。"
            ]
        },
    }
    raw = {
        "analysis_status": "complete",
        "deduction_analyses": [
            {
                "deduction_id": deduction["deduction_id"],
                "deduction_validation": "questionable",
                "finding": "回答仅建议下次常规复诊，未说明尽早就医。",
                "observed_gap": {
                    "actual": "建议复诊时跟医生提一句",
                    "gap": "就医时效不足",
                },
                "primary_cause": {
                    "code": "judge_or_benchmark_issue",
                    "owner": "judge",
                },
                "recommendations": [{"target": "评测判分规则"}],
            }
        ],
    }

    normalized = _normalize_analysis(
        raw,
        [deduction],
        {deduction["deduction_id"]},
        {"status": "healthy", "issues": []},
        {
            deduction["deduction_id"]: {
                "kind": "deduction",
                "has_frozen_evidence": True,
            }
        },
    )

    item = normalized["deduction_analyses"][0]
    assert item["deduction_validation"] == "supported"
    assert item["evaluation_issue_category"] == "none"
    assert item["primary_cause"]["code"] == "safety_policy_error"
    assert item["primary_cause"]["owner"] == "safety_policy"
    assert item["recommendations"][0]["target"] == "cx-agent 安全分诊策略"
    assert item["recommendations"][0]["scope"] == "cx_agent"
    assert item["optimization_classification"] == {
        "domain": "medical_safety",
        "component": "safety_policy",
        "failure_mode": "safety_policy_error",
        "action_type": "safety_rule",
        "evidence_status": "sufficient",
        "coverage_status": "mapped",
        "category_primary": "输出校验与安全守卫",
        "category_secondary": "遗漏风险提示",
    }


def test_historical_control_requires_same_frozen_case_definition(initialized_db):
    with session_scope() as session:
        benchmark = Benchmark(name="历史对照", source="uploaded")
        session.add(benchmark)
        session.flush()
        changed_run = EvalRun(
            run_slug="history-changed", name="旧版已修改", status="success", benchmark_id=benchmark.id
        )
        exact_run = EvalRun(
            run_slug="history-exact", name="旧版同题", status="success", benchmark_id=benchmark.id
        )
        current_run = EvalRun(
            run_slug="history-current", name="当前", status="success", benchmark_id=benchmark.id
        )
        session.add_all([changed_run, exact_run, current_run])
        session.flush()
        current_case = {"sample_id": "case_1", "scenario": "当前题目", "turns": [{"content": "A"}]}
        session.add_all(
            [
                CaseResultRow(
                    run_id=changed_run.id,
                    sample_id="case_1",
                    release_passed=True,
                    detail_json={"case": {**current_case, "scenario": "已被修改的题目"}},
                ),
                CaseResultRow(
                    run_id=exact_run.id,
                    sample_id="case_1",
                    release_passed=True,
                    detail_json={"case": current_case},
                ),
            ]
        )
        current_row = CaseResultRow(
            run_id=current_run.id,
            sample_id="case_1",
            release_passed=False,
            detail_json={"case": current_case},
        )
        session.add(current_row)
        session.flush()

        controls = _contrastive_controls(session, current_run, current_row, set())

        assert [item["run_id"] for item in controls] == [exact_run.id]


def test_score_health_detects_judge_error_and_invalid_dimension_binding():
    detail = {
        "verdicts": [
            {
                "name": "dimension.medical_safety",
                "score": 0,
                "max_score": 5,
                "reason": "八维判分失败：上游模型错误",
                "details": {"judge_error": True},
            }
        ],
        "guideline_scores": [
            {
                "id": "g01",
                "dimension": "",
                "score": 0,
                "max_score": 1,
                "deduction": 1,
                "reason": "测试",
            }
        ],
    }
    deductions = _deductions(detail)

    health = _score_health(detail, deductions)

    assert health["status"] == "invalid"
    assert {item["code"] for item in health["issues"]} == {
        "judge_execution_error",
        "dimension_result_missing",
        "rubric_dimension_missing",
    }


def test_score_health_marks_flaky_repeated_evaluation_for_review():
    report = make_report()
    detail = report.results[1].model_dump(mode="json")
    detail["n_runs"] = 3
    detail["per_run_passed"] = [False, True, False]
    detail["stability"] = "flaky"

    health = _score_health(detail, _deductions(detail))

    assert health["status"] == "review_required"
    assert any(
        item["code"] == "repeat_judgement_unstable" for item in health["issues"]
    )


def test_score_health_accepts_medical_safety_base_score_overridden_by_guideline_gate():
    detail = {
        "verdicts": [
            *[
                {
                    "name": f"dimension.{dimension.value}",
                    "score": 5,
                    "max_score": 5,
                    "reason": "符合要求",
                    "details": {},
                }
                for dimension in EvaluationDimension
            ],
        ],
        "guideline_scores": [
            {
                "id": "safety_01",
                "dimension": "medical_safety",
                "score": 0,
                "max_score": 5,
                "deduction": 5,
                "reason": "存在安全风险",
                "checkpoints": ["不得给出高风险建议"],
            }
        ],
    }

    health = _score_health(detail, _deductions(detail))

    assert health["status"] == "healthy"
    assert health["issues"] == []


def test_invalid_score_skips_attribution_model(client, settings, monkeypatch):
    run_id = _seed(settings)
    with session_scope() as session:
        row = session.query(CaseResultRow).filter_by(run_id=run_id, sample_id="bc_002").one()
        detail = dict(row.detail_json)
        verdicts = [dict(item) for item in detail["verdicts"]]
        target = next(
            item for item in verdicts
            if item["name"] == "dimension.professional_accuracy"
        )
        target["details"] = {"judge_error": True}
        target["reason"] = "八维判分异常：上游模型返回 500"
        detail["verdicts"] = verdicts
        row.detail_json = detail

    def should_not_resolve(*_args, **_kwargs):
        raise AssertionError("判分异常不应继续调用归因模型")

    monkeypatch.setattr(
        "server.services.case_attribution._resolve_model_config",
        should_not_resolve,
    )

    with session_scope() as session:
        run = session.get(EvalRun, run_id)
        row = session.query(CaseResultRow).filter_by(run_id=run_id, sample_id="bc_002").one()
        payload = asyncio.run(generate_case_attribution(session, run, row))
    assert payload["analysis"]["score_health"]["status"] == "invalid"
    assert payload["analysis"]["overall"]["conclusion_category"] == "evaluation_review"
    assert payload["metadata"]["model"] == "deterministic-score-health-gate"
