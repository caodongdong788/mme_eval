# CX SIT Service Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move new MME evaluations off the retired `10.30.7.71` SIT container and keep historical CX replay links usable through the current SIT domain.

**Architecture:** New evaluations use the stable public SIT origin `https://sit-cx.senzco.com`. Historical result JSON remains immutable; the case-detail read boundary rewrites only the retired origin to the stable origin before returning it to the frontend. Current URLs, paths, queries, fragments, exports, and stored JSON are left unchanged.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, pytest, React/Vitest.

---

### Task 1: Protect the historical-link compatibility contract

**Files:**
- Modify: `tests/server/test_langfuse_trace_link.py`
- Modify: `server/services/case_export.py`

- [ ] **Step 1: Write the failing API test**

Seed a case whose `trace.cx_evaluation_share_url` is `http://10.30.7.71/s/evaluation-token?source=mme#turn-1`. Assert the case-detail API returns `https://sit-cx.senzco.com/s/evaluation-token?source=mme#turn-1`, while a second database read still contains the original URL.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `.venv/bin/pytest -q tests/server/test_langfuse_trace_link.py -k legacy_cx_share`

Expected: FAIL because the API currently returns the retired origin unchanged.

- [ ] **Step 3: Implement the smallest read-boundary rewrite**

In `get_case_detail_json`, parse the URL and replace the origin only when the scheme/host are exactly `http://10.30.7.71`. Preserve the path, query, and fragment. Operate on the compact response copy rather than `row.detail_json`.

- [ ] **Step 4: Run the focused tests**

Run: `.venv/bin/pytest -q tests/server/test_langfuse_trace_link.py`

Expected: PASS.

### Task 2: Move new evaluation traffic to the stable SIT origin

**Files:**
- Modify: `config.yaml`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Add a configuration regression test**

Load the repository `config.yaml` and assert `adapter.cx_agent.base_url == "https://sit-cx.senzco.com"`.

- [ ] **Step 2: Run the test and verify failure**

Run: `.venv/bin/pytest -q tests/test_config.py -k repository_cx_agent`

Expected: FAIL with the existing `http://10.30.7.71` value.

- [ ] **Step 3: Update the configuration**

Replace the retired IP origin with `https://sit-cx.senzco.com`; do not change endpoint paths, tokens, RAG behavior, or scoring configuration.

- [ ] **Step 4: Run configuration and adapter tests**

Run: `.venv/bin/pytest -q tests/test_config.py tests/test_adapter_registry.py tests/test_cx_agent_adapter.py`

Expected: PASS.

### Task 3: Verify the complete MME change

**Files:**
- Verify only.

- [ ] **Step 1: Run backend regression checks**

Run: `.venv/bin/pytest -q tests/server/test_langfuse_trace_link.py tests/test_config.py tests/test_cx_agent_adapter.py`

Expected: PASS.

- [ ] **Step 2: Verify backend import**

Run: `.venv/bin/python -c "import server.app"`

Expected: exit 0.

- [ ] **Step 3: Build the frontend**

Run: `cd frontend && npm run build`

Expected: exit 0.

- [ ] **Step 4: Review the final diff**

Confirm the diff contains only the stable-origin configuration, the narrow historical-origin rewrite, tests, and this plan. Confirm no stored evaluation result is mutated.
