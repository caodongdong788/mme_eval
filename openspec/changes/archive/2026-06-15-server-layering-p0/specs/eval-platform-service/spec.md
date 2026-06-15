## ADDED Requirements

### Requirement: Run helper logic MUST reside in server services layer

Run-related query and case-row enrichment logic that was in `server/routers/runs/_helpers.py` MUST be implemented in `server/services/runs.py` and `server/services/case_query.py`. HTTP handlers MUST import from these service modules (or the `_helpers` re-export shim). REST paths, status codes, and response JSON MUST remain unchanged.

#### Scenario: Review queue API unchanged

- **WHEN** a client requests `GET /api/runs/{id}/review-queue` after P0
- **THEN** the response MUST match pre-refactor filtering and `reasons` semantics for the same run data
