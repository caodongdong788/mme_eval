## ADDED Requirements

### Requirement: CLI evaluation behavior MUST remain unchanged during layering refactor

Structural refactors in P0 MUST NOT alter CLI commands, flags, exit codes, or `report.json` / artifact formats produced by `medeval run`, `medeval rejudge`, or `medeval validate`.

#### Scenario: Dry-run still succeeds

- **WHEN** `medeval run --config config.yaml --dry-run` is executed after P0
- **THEN** the command MUST exit 0 with the same assembly behavior as before refactor
