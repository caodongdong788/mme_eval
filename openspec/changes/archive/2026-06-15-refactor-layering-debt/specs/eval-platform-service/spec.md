## ADDED Requirements

### Requirement: Platform MUST expose judge verdict Chinese labels via config API

The eval platform service MUST expose `GET /api/config/judge-verdict-labels` returning a JSON object mapping judge verdict names (e.g. `hard_gate.red_flag`, `llm.empathy`) to Chinese display labels. Labels MUST be sourced from `medeval.judge_labels` as the single trust source. Existing REST paths and response schemas for other endpoints MUST NOT change.

#### Scenario: Fetch judge verdict labels

- **WHEN** a client requests `GET /api/config/judge-verdict-labels`
- **THEN** the response MUST be HTTP 200 with a JSON object containing at least `hard_gate.red_flag` and `llm.empathy` keys

### Requirement: Token cost computation MUST use a single shared implementation

Per-case token and cost computation for DB ingest MUST call the shared function in `medeval.reporter.token_cost`. Run-level token aggregation in the reporter MUST use the same cost formula helper. Numeric outputs for identical inputs MUST remain unchanged from pre-refactor behavior.

#### Scenario: Ingest token cost unchanged

- **WHEN** `build_case_row` processes a `CaseResult` with known token usage and pricing
- **THEN** `total_tokens` and `cost` columns MUST match pre-refactor characterization fixtures
