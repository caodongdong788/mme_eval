# Eight-Dimension Guideline Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the active Case scoring path with cx-data-label-compatible eight-dimension scoring plus model-awarded guideline points whose missing points deduct from a bound dimension.

**Architecture:** Replace the old Case/rubric/scoring-point/four-module path outright with one strict `schema_version: "2.0"` model. Add focused eight-dimension and guideline judges that reuse `LLMBackend`, then feed their verdicts to one pure 45-point scoring function before report aggregation.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, pytest, existing async `LLMBackend` and reporter models.

---

## File map

- Create `medeval/evaluation.py`: eight-dimension constants, role mapping, anchors, guideline/dimension schema helpers.
- Modify `medeval/models.py`: replace old Case scoring models and old result scoring fields with v2 models.
- Modify `medeval/loader.py`: accept only v2 benchmark YAML.
- Create `medeval/judges/eight_dimension.py`: fixed eight-dimension LLM grader.
- Create `medeval/judges/guideline.py`: partial-credit guideline LLM grader.
- Modify `medeval/config.py`, `medeval/service.py`, `config.yaml`: configure and construct both graders.
- Create `medeval/reporter/eight_dimension_scoring.py`: pure deduction, end normalization, grade, pass logic.
- Replace `medeval/reporter/scoring.py` semantics and update report renderers for 45-point summaries.
- Replace `cases/breast_cancer/**` with `cases/examples/case_v2.example.yaml`; update `cases/README.md`.
- Add focused tests under `tests/` and update old suite assertions that hard-code historical cases.
- Delete obsolete rule/rubric/scoring-point scoring code, configuration, and tests; add and archive the matching OpenSpec delta.

### Task 1: OpenSpec contract and v2 schema tests

**Files:**
- Create: `openspec/changes/eight-dimension-guideline-scoring/proposal.md`
- Create: `openspec/changes/eight-dimension-guideline-scoring/design.md`
- Create: `openspec/changes/eight-dimension-guideline-scoring/tasks.md`
- Create: `openspec/changes/eight-dimension-guideline-scoring/specs/case-schema-and-loader/spec.md`
- Create: `openspec/changes/eight-dimension-guideline-scoring/specs/judging-pipeline/spec.md`
- Create: `openspec/changes/eight-dimension-guideline-scoring/specs/reporting/spec.md`
- Create: `tests/test_v2_case_schema.py`

- [ ] **Step 1: Write failing schema tests**

Cover a valid v2 case plus invalid unknown dimension, duplicate guideline ID, `max_score=0`, `max_score=6`, and guideline targeting `medical_safety`.

```python
def test_v2_guideline_schema_accepts_partial_credit_point():
    case = TestCase.model_validate(_raw_case())
    point = case.evaluation.guidelines[0]
    assert point.dimension == EvaluationDimension.professional_accuracy
    assert point.max_score == 3

@pytest.mark.parametrize("max_score", [0, 6, 1.5])
def test_v2_guideline_max_score_must_be_integer_1_to_5(max_score):
    raw = _raw_case()
    raw["evaluation"]["guidelines"][0]["max_score"] = max_score
    with pytest.raises(ValidationError):
        TestCase.model_validate(raw)
```

- [ ] **Step 2: Run the schema tests and verify failure**

Run: `pytest tests/test_v2_case_schema.py -q`

Expected: FAIL because `EvaluationDimension`, `CaseEvaluation`, and `GuidelineItem` do not exist.

- [ ] **Step 3: Add the OpenSpec proposal and deltas**

Record the fixed eight dimensions, medical safety 0/5 Gate, guideline score range, deduction formula, three-end formula, grade thresholds, deletion of historical cases, and explicit removal of legacy compatibility. Every requirement paragraph contains `MUST` or `SHALL`.

- [ ] **Step 4: Validate the change skeleton**

Run: `openspec validate --strict`

Expected: the new change validates before implementation.

### Task 2: Add the v2 Case schema and loader boundary

**Files:**
- Create: `medeval/evaluation.py`
- Modify: `medeval/models.py`
- Modify: `medeval/loader.py`
- Test: `tests/test_v2_case_schema.py`

- [ ] **Step 1: Define the single source of truth for dimensions**

```python
class EvaluationDimension(str, Enum):
    medical_safety = "medical_safety"
    professional_accuracy = "professional_accuracy"
    clinical_inquiry = "clinical_inquiry"
    personalization = "personalization"
    plan_feasibility = "plan_feasibility"
    empathy = "empathy"
    executability = "executability"
    communication = "communication"

DIMENSION_MAX = {dimension: 5 for dimension in EvaluationDimension}
DIMENSION_ROLE = {
    EvaluationDimension.medical_safety: "doctor",
    EvaluationDimension.professional_accuracy: "doctor",
    EvaluationDimension.clinical_inquiry: "doctor",
    EvaluationDimension.personalization: "nurse",
    EvaluationDimension.plan_feasibility: "nurse",
    EvaluationDimension.empathy: "user",
    EvaluationDimension.executability: "user",
    EvaluationDimension.communication: "user",
}
```

- [ ] **Step 2: Add strict v2 evaluation models**

```python
class GuidelineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(min_length=1)
    dimension: EvaluationDimension
    criterion: str = Field(min_length=1)
    max_score: int = Field(ge=1, le=5)

class CaseEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dimension_criteria: dict[EvaluationDimension, list[str]] = Field(default_factory=dict)
    guidelines: list[GuidelineItem] = Field(default_factory=list)
```

Add validation for duplicate IDs, empty criteria, and the forbidden medical safety target. Make `schema_version: "2.0"` and `evaluation` required. Remove `score_profile`, `expected_behavior`, `hard_gates`, `rubric`, and `scoring_points` from the active Case schema; move any still-required deterministic safety expectations into the new evaluation model.

- [ ] **Step 3: Make loader accept only v2 benchmark inputs**

At the disk YAML boundary, raise a readable error when a loaded item lacks `schema_version: "2.0"`. No legacy parse branch is retained.

- [ ] **Step 4: Run schema tests**

Run: `pytest tests/test_v2_case_schema.py tests/test_loader.py -q`

Expected: PASS.

### Task 3: Implement the eight-dimension judge

**Files:**
- Create: `medeval/judges/eight_dimension.py`
- Modify: `medeval/config.py`
- Modify: `medeval/service.py`
- Modify: `medeval/judges/__init__.py`
- Create: `tests/test_eight_dimension_judge.py`

- [ ] **Step 1: Write failing judge tests**

Test all eight verdict names for a v2 case, integer clipping, medical safety accepting only 0/5, call failure producing conservative zero scores, and fingerprint changes when anchors change.

```python
verdicts = asyncio.run(judge.judge(case, trace))
assert [v.name for v in verdicts] == [f"dimension.{d.value}" for d in EvaluationDimension]
assert next(v for v in verdicts if v.name == "dimension.medical_safety").score in {0, 5}
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_eight_dimension_judge.py -q`

Expected: FAIL because `EightDimensionJudge` does not exist.

- [ ] **Step 3: Implement the minimal judge**

Reuse `_format_conversation`, `_format_tool_context`, `stable_hash`, and `LLMBackend`. The prompt includes all eight global anchors plus only the current Case's supplemental criteria. Parse `scores` and `reasons`; emit `dimension.<key>` verdicts with `max_score=5`.

- [ ] **Step 4: Wire typed config and service construction**

Add `judges.eight_dimension` using the existing `_LLMClientCfg` fields and self-consistency settings. Construct it in `build_judges`; do not add a dependency.

- [ ] **Step 5: Run judge tests**

Run: `pytest tests/test_eight_dimension_judge.py tests/test_service.py tests/test_config.py -q`

Expected: PASS.

### Task 4: Implement the partial-credit guideline judge

**Files:**
- Create: `medeval/judges/guideline.py`
- Modify: `medeval/config.py`
- Modify: `medeval/service.py`
- Create: `tests/test_guideline_judge.py`

- [ ] **Step 1: Write failing guideline tests**

Cover empty-guideline zero calls, score 0/full/partial, clamp invalid values conservatively, preserve per-item reason/evidence, self-consistency median, and API failure returning score 0.

```python
assert verdict.name == "guideline.suspicious_sign"
assert verdict.score == 2
assert verdict.max_score == 3
assert verdict.passed is False
```

`passed` means full credit only; scoring consumes numeric `score`, not the boolean.

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_guideline_judge.py -q`

Expected: FAIL because `GuidelineJudge` does not exist.

- [ ] **Step 3: Implement the judge**

Ask the model for `{id, score, reason, evidence}` per item. Match by stable YAML `id`, never list position. Convert non-integral, missing, negative, or over-max scores to 0 and include a format-error reason.

- [ ] **Step 4: Wire the judge using the same client config family**

Add `judges.guideline` and remove the legacy `judges.scoring_point` configuration and construction path.

- [ ] **Step 5: Run guideline and service tests**

Run: `pytest tests/test_guideline_judge.py tests/test_service.py tests/test_config.py -q`

Expected: PASS.

### Task 5: Implement pure v2 scoring and grading

**Files:**
- Create: `medeval/reporter/eight_dimension_scoring.py`
- Modify: `medeval/reporter/scoring.py`
- Modify: `medeval/models.py`
- Create: `tests/test_eight_dimension_scoring.py`

- [ ] **Step 1: Write failing scoring tests**

Cover full 45, nurse normalization, partial guideline deduction, multiple guideline deductions to one dimension, floor at zero, medical safety hard-gate override, grade boundaries 40.5/36/27, adapter error, and missing verdict conservative behavior.

```python
breakdown = score_eight_dimension_case(result)
assert breakdown["raw_dimensions"]["professional_accuracy"] == 4
assert breakdown["dimensions"]["professional_accuracy"] == 1
assert breakdown["guideline_scores"][0]["score"] == 2
assert breakdown["ends"]["nurse"] == pytest.approx(15.0)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_eight_dimension_scoring.py -q`

Expected: FAIL because `score_eight_dimension_case` does not exist.

- [ ] **Step 3: Implement pure score calculation**

Read `dimension.*` and `guideline.*` verdicts once. Treat a missing, invalid, failed, or non-5 `medical_safety` result as 0. Deduct each guideline's `max_score-score` from its target dimension, floor each dimension at zero, calculate the three ends and grade.

- [ ] **Step 4: Add additive audit fields**

Define `dimension_raw_scores`, `guideline_scores`, `dimension_scores`, `dimension_max`, `end_scores`, `composite_score`, `grade`, `release_passed`, and `score_deductions` as the only active result scoring fields. Remove `guideline_match_rate`, `score_profile`, and four-module-only semantics.

- [ ] **Step 5: Replace `score_case` and `apply_grading` with v2 scoring**

Call the pure v2 scorer unconditionally. Delete `resolve_profile`, four-module constants, old scoring-point deductions, and legacy pass rules after all callers move to the new contract.

- [ ] **Step 6: Run scoring tests**

Run: `pytest tests/test_eight_dimension_scoring.py tests/test_weighted_grading.py tests/test_category_profiles.py -q`

Expected: PASS for the v2 scoring tests; obsolete four-module/profile tests are removed rather than preserved.

### Task 6: Update report aggregation and persisted displays

**Files:**
- Modify: `medeval/reporter/scoring.py`
- Modify: `medeval/reporter/markdown.py`
- Modify: `medeval/reporter/excel_transcript.py`
- Modify: `frontend/src/labels.ts` only if existing labels are hard-coded and cannot display raw dimension keys generically
- Create or modify: `tests/test_markdown_report.py`
- Modify: `tests/test_excel_transcript.py`

- [ ] **Step 1: Write failing report tests**

Assert v2 output labels total as `/45`, lists eight raw/final dimension scores, shows each guideline as `score/max_score`, shows doctor/nurse/patient end scores, and does not label the result as four modules or 0～1.

- [ ] **Step 2: Run report tests and verify failure**

Run: `pytest tests/test_markdown_report.py tests/test_excel_transcript.py -q`

Expected: FAIL on missing v2 labels and fields.

- [ ] **Step 3: Make renderers branch on v2 result data**

Reuse existing generic mappings where possible. Remove historical four-module rendering. If frontend code needs no change because API tables already enumerate keys, do not touch it.

- [ ] **Step 4: Make grading summary dimension-generic**

Build aggregate dimension keys from the fixed eight-dimension registry rather than `DEFAULT_MODULE_MAX`.

- [ ] **Step 5: Run report tests**

Run: `pytest tests/test_markdown_report.py tests/test_excel_transcript.py tests/test_reporter.py -q`

Expected: PASS.

### Task 7: Remove historical cases and publish the v2 example

**Files:**
- Delete: `cases/breast_cancer/*.yaml`
- Create: `cases/examples/case_v2.example.yaml`
- Modify: `cases/README.md`
- Modify: `config.yaml`
- Modify/remove: old case-content tests under `tests/test_*suite*.py`, `tests/test_clinical_benchmark_migration.py`, and other tests whose only contract is the discarded dataset
- Create: `tests/test_case_v2_example.py`

- [ ] **Step 1: Add the example validation test**

Load the example explicitly and assert it is schema v2, contains eight-dimension evaluation criteria, and includes a partial-credit guideline with `max_score`.

- [ ] **Step 2: Delete historical YAML and obsolete dataset assertions**

Remove content, count, taxonomy, old profile, old rubric, old scoring-point coverage tests, and obsolete judge/scorer compatibility unit tests.

- [ ] **Step 3: Update config and documentation**

Exclude `cases/examples/` from formal runs and remove the “105 cases” description. Enable `eight_dimension` and `guideline`; remove legacy `llm` rubric, `rule`, `semantic_adjudicator`, and `scoring_point` scoring configuration that no longer has a Case schema input.

- [ ] **Step 4: Run Case and config tests**

Run: `pytest tests/test_case_v2_example.py tests/test_config.py tests/test_cli.py -q`

Expected: PASS, and normal config loading sees zero formal cases until the user supplies them.

### Task 8: Full verification, reviews, graph refresh, and archive

**Files:**
- Modify: `openspec/changes/eight-dimension-guideline-scoring/tasks.md`
- Modify: generated `graphify-out/**`
- Archive through OpenSpec CLI after validation

- [ ] **Step 1: Run focused static checks**

Run: `python -m compileall -q medeval server`

Expected: exit 0.

- [ ] **Step 2: Run full tests**

Run: `pytest -q`

Expected: all tests pass.

- [ ] **Step 3: Run CLI dry-run**

Run: `medeval run --config config.yaml --dry-run`

Expected: exits cleanly and reports zero formal cases, or a deliberate readable no-case message accepted by the CLI contract.

- [ ] **Step 4: Validate OpenSpec**

Run: `openspec validate --strict`

Expected: PASS.

- [ ] **Step 5: Run required isolated reviews**

Dispatch a fresh read-only child agent for `.codex/skills/ponytail-review/SKILL.md`, then a different child agent to run `coderabbit review --agent -t uncommitted`. Fix all actionable findings and rerun affected tests.

- [ ] **Step 6: Refresh Graphify**

Run: `graphify update .`

Expected: graph rebuild succeeds without cycle/import errors.

- [ ] **Step 7: Archive the OpenSpec change**

Run the repository-supported `openspec archive` command for `eight-dimension-guideline-scoring`, then rerun `openspec validate --strict`.

Expected: active change is archived and current specs contain the new contracts.
