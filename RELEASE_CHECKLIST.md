# BankFlow Resume & Portfolio Release Checklist

## Release Scope

Deliver BankFlow as a reproducible, tested Python/PostgreSQL batch ETL and analytics warehouse using synthetic banking data:
- Synthetic CSV generation with reproducible defect scenarios.
- Raw staging ingestion with batch registration and row-level lineage.
- Contract validation engine with quarantine inventory and data-quality issues tracking.
- Dimensional warehouse star schema with conformed dimensions and transaction facts.
- Database-enforced idempotency protecting identical replays and rejecting conflicting payloads.
- Traceable batch reconciliation auditing row counts and gross monetary totals.
- Conformed analytical reporting schema in PostgreSQL (`reporting.*`).
- Secure, read-only REST API backend (`FastAPI`/`Uvicorn`) with least-privilege database role.
- Automated CI pipeline on GitHub Actions with mandatory PostgreSQL integration tests.
- Reproducible demonstration guide and interview walk-through (`docs/demo_walkthrough.md`).

## Verification & Release Gate

- [x] Baseline confirmed: Base branch `main` at PR #9 merge commit `374db5f53de83c315b7d200adbaffd377faf4f0a` with post-merge CI verified green (Run #39033345647).
- [x] Working tree clean; uncommitted user work preserved.
- [x] Install package and extras cleanly: `python -m pip install -e ".[dev,api]"` in Python 3.12 virtual environment.
- [x] Start PostgreSQL using `docker compose up -d --wait`, then verify `python -m bankflow test-connection` and `test-connection --test-db`.
- [x] Initialize schemas using `python -m bankflow init-db --test-db`.
- [x] Run full test suite with mandatory integration tests: `$env:BANKFLOW_REQUIRE_INTEGRATION_TESTS = "1"; python -m pytest tests -v` (**168 passed, 0 skipped, 0 failed**).
- [x] Zero skips accepted: all integration tests executed against live PostgreSQL test database.
- [x] Verify clean data end-to-end: generated clean dataset, ran `demo-clean-001`, verified `SUCCEEDED` (170 staged, 170 valid, 100 facts, `RECONCILED`).
- [x] Verify idempotent replay: re-ran same data under `demo-clean-001-replay`, verified 0 facts inserted, 100 replays skipped, facts not duplicated.
- [x] Verify defective-data workflow: generated defective dataset, ran `demo-defects-001`, verified `SUCCEEDED_WITH_REJECTIONS` (14 quarantined, quality issues recorded).
- [x] Verify reporting views: queried `daily`, `deposit-withdrawal`, `branch-channel`, `quality`, `batches`, and `quarantine` via CLI and direct SQL.
- [x] Verify read-only API: tested `bankflow serve --test-db`, probed `/api/v1/health` and `/api/v1/overview`, verified read-only enforcement and least-privilege role.
- [x] Verify repository hygiene: `git diff --check` passes with zero errors; no `.env`, credentials, real data, database files, or generated CSVs committed.
- [x] Documentation synchronized: updated `README.md`, `HUMAN_SETUP.md`, `docs/architecture.md`, `docs/data_dictionary.md`, `docs/demo_walkthrough.md`, `DEVELOPMENT_CHECKLIST.md`, and `PHASE_LOG.md`.
- [x] Strengthened test database guard: added `stage`, `staging`, and `release` to forbidden production tokens in `DatabaseConfig.is_test_database()`.
- [x] Strengthened CI: added `git diff --check` hygiene check to `.github/workflows/ci.yml`.

## Defer Until After Initial Release

- Cloud scheduling, managed cloud databases, and secret manager cloud deployment.
- Live public internet hosting of the API backend (hosted Lovable console remains in synthetic Demo Mode boundary).
- Additional analytical dimensions and streaming ingestion (Kafka/Flink).
- Automated performance benchmarking beyond reproducible test dataset measurements.
