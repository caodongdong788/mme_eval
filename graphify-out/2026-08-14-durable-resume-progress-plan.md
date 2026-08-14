# Durable evaluation resume progress plan

## Problem

When a production deploy restarts the evaluation worker, the durable job is reclaimed and its
conversation traces are reused. The in-memory progress object and incremental report accumulator,
however, restart from zero. Already judged Case rows remain in Postgres but are judged again, so the
visible percentage and run summary temporarily move backwards.

## Implementation

1. Load valid, already persisted `CaseResult` objects for the in-place run.
2. Seed the incremental report accumulator with those results so partial summaries never shrink.
3. Pass the completed results into the evaluator, prefill Case/Judge progress, and skip their Judge
   callbacks while still replaying persisted traces into the finalized trace artifact.
4. Restore the last persisted percentage as a monotonic floor when a durable job is reclaimed.
5. Add regression tests for result loading, summary merging, skipped judging, and monotonic progress.

## Validation

- Focused resume/progress tests.
- Full backend test suite.
- Frontend tests and production build (the API payload shape is unchanged).
- `git diff --check`.
