## ADDED Requirements

### Requirement: CLI MUST provide `import-feishu` to convert Feishu spreadsheets into case YAML

The CLI MUST expose `medeval import-feishu` (and `scripts/import_benchmark_from_feishu.py` as a thin wrapper) that reads a Feishu spreadsheet via `lark-cli sheets +read`, parses rows with headers `测试内容` / `得分点明细` / `轮数` / `第N轮 (用户+Bot)`, and writes a `TestCase` YAML list plus an `import_report.json`. When `得分点明细` is empty, the command MUST invoke the configured LLM judge client to generate `expected_behavior`, `hard_gates`, `rubric`, and `scoring_points`. When `得分点明细` is present, the command MUST parse `scoring_points` deterministically and MAY use the LLM only for remaining fields. The command MUST run `medeval validate` on success unless `--skip-validate` is set.

#### Scenario: Parse scoring points from sheet cell

- **WHEN** a row contains numbered scoring point lines with a negative marker such as `负分` or `惩罚`
- **THEN** the importer MUST emit `scoring_points` with negative `points` for those lines and positive `points` for other lines

#### Scenario: Skip enrich produces skeleton only

- **WHEN** `medeval import-feishu` is run with `--no-enrich`
- **THEN** output YAML MUST contain `turns` and `notes` but MUST NOT call any LLM
