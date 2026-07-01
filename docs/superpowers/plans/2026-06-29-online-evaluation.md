# Online Evaluation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a separate "线上评测" platform entry for real online conversations with 10-point companionship-oriented scoring.

**Architecture:** Keep online evaluation separate from benchmark `EvalRun`. Add dedicated ORM tables, schemas, service, router, frontend API/hook/page, and reuse existing Dashboard Surface components.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, React 18, TypeScript, Ant Design 5.

---

### Task 1: Backend API And Persistence

**Files:**
- Modify: `server/models_db.py`
- Modify: `server/schemas.py`
- Create: `server/services/online_evals.py`
- Create: `server/routers/online_evals.py`
- Modify: `server/app.py`
- Test: `tests/server/test_online_evals.py`

- [x] Write failing API tests for creating/listing online eval batches.
- [x] Add `OnlineEval` and `OnlineEvalCase` ORM models.
- [x] Add request/response schemas for batch and case result payloads.
- [x] Implement deterministic v1 scoring with Gate status, five dimension scores, risk tags, evidence, and suggestions.
- [x] Add thin router and register it in `create_app()`.
- [x] Run `pytest tests/server/test_online_evals.py -q`.

### Task 2: Frontend Entry

**Files:**
- Modify: `frontend/src/api/types.ts`
- Create: `frontend/src/api/onlineEvals.ts`
- Modify: `frontend/src/api/index.ts`
- Create: `frontend/src/hooks/useOnlineEvalsPage.ts`
- Create: `frontend/src/pages/OnlineEvalsPage.tsx`
- Modify: `frontend/src/App.tsx`

- [x] Add API types and client methods for online eval list/create/detail.
- [x] Add page hook for form submission, history loading, and detail drawer loading.
- [x] Add `/online-evals` route and sidebar menu item.
- [x] Render create form, history table, and detail drawer with 10-point dimension bars.
- [x] Run `cd frontend && npm run verify`.

### Task 3: Validation And Governance

**Files:**
- Create: `openspec/changes/add-online-evaluation/*`

- [x] Add OpenSpec proposal, tasks, and service/dashboard deltas.
- [ ] Run OpenSpec strict validation when a CLI entrypoint is available.
- [ ] Run read-only ponytail-review subagent.
- [ ] Run read-only CodeRabbit subagent or record tool unavailability.
- [ ] Refresh Graphify or record protection/API-key blocker.
