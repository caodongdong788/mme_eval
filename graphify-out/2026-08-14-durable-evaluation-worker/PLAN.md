# Durable Evaluation Worker Implementation Plan

## Goal

Keep evaluation runs alive across web deployments and automatically resume unfinished work after worker restarts without re-running persisted successful traces.

## Invariants

- API processes never execute long-running evaluation jobs in production worker mode.
- Every submitted evaluation job has a durable database row before the API returns.
- A database lease allows at most one worker to own a job at a time.
- Completed traces and Case results remain reusable checkpoints; recovery only fills missing work.
- Secrets are not copied into queue payloads. Saved model references or environment-backed secret names are resolved by the worker.
- User cancellation is terminal and must not be confused with deployment interruption.
- Existing in-process execution remains available for local development and unit tests.

## Phase 1 — restart-safe recovery

- [x] Persist a serializable execution specification for every evaluation job.
- [x] Reserve the run output directory and execution plan before work starts.
- [x] Replace startup orphan failure with durable queue recovery.
- [x] Rebuild an interrupted normal evaluation as an in-place resume job when checkpoints exist.
- [x] Keep queued work queued and retry stale leased work after its lease expires.
- [x] Add tests proving completed traces are reused after recovery.

## Phase 2 — independent worker

- [x] Add a Postgres/SQLite-compatible durable job table with status, attempts, lease owner, lease expiry, heartbeat, payload and errors.
- [x] Add a worker process that claims jobs with a lease, heartbeats while running, and renews/requeues stale leases.
- [x] Make the API-side runner enqueue only and read queue/progress state from the database.
- [x] Register serializable builders for normal evaluation, resume, rejudge and Case retry jobs.
- [x] Add a separate `worker` Compose service sharing Postgres, configuration, outputs and uploads.
- [x] Deploy `app` without restarting `worker`; deploy worker explicitly only when worker code changes.
- [x] Add graceful worker shutdown so active work is checkpointed and reclaimed rather than marked failed.

## Verification

- [x] Queue claim is exclusive and stale leases are recoverable.
- [x] API submission survives API process shutdown.
- [x] Worker restart resumes the same run and does not rerun persisted successful traces.
- [x] Cancellation prevents later reclaim.
- [x] Full backend suite passes (510 passed, 3 skipped).
- [x] Frontend unit tests (110 passed) and production build pass. Existing standards/type errors are recorded separately.
- [x] Docker Compose renders both `app` and `worker` with shared persistent storage.
