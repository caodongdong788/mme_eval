## ADDED Requirements

### Requirement: Platform domain routers MUST delegate to service layer

HTTP handlers for judge models, dashboard trends, config release thresholds, HITL review, and pairwise comparison MUST delegate business logic to `server/services/*` modules. Routers MUST NOT execute SQLAlchemy queries directly after P1. REST paths and response JSON MUST remain unchanged.

#### Scenario: Judge model CRUD unchanged

- **WHEN** a client performs create/list/update/delete on `/api/judge-models` after P1
- **THEN** HTTP status codes and response bodies MUST match pre-refactor behavior
