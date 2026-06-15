## ADDED Requirements

### Requirement: Benchmark and run catalog routers MUST delegate to service layer

After P2, `routers/benchmarks.py`, `routers/runs/crud.py`, and `routers/runs/cases.py` MUST NOT contain SQLAlchemy queries or multi-step business orchestration; they MUST call `server/services/benchmark_catalog.py`, `server/services/runs.py`, and `server/services/case_export.py` respectively. REST behavior MUST remain unchanged.

#### Scenario: Create run API unchanged

- **WHEN** `POST /api/runs` is called with a valid payload after P2
- **THEN** the response MUST match pre-refactor status code and `RunSummaryOut` fields
