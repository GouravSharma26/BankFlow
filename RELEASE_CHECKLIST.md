# BankFlow resume-release checklist

## Release scope

Ship BankFlow as a Python/PostgreSQL CLI data-engineering project: synthetic CSV generation, staging/lineage, validation and quarantine, dimensional warehouse loading, replay protection, reconciliation, and reusable SQL reports. Do not represent it as an already-hosted website or BI dashboard.

## Must pass before adding it to the resume

- [x] Confirm the current branch is `phase/3-warehouse-loading` and includes the latest replay-integrity/concurrency commits (head: `cdb4ea8`).
- [x] Run `git status --short`; preserve uncommitted user changes.
- [x] Install with `python -m pip install -e ".[dev]"` in a clean Python 3.12 environment.
- [x] Start PostgreSQL using `docker compose up -d --wait`, then verify `python -m bankflow test-connection`.
- [x] Initialize using `python -m bankflow init-db`.
- [x] Run the full suite with the dedicated test database: `python -m pytest tests -v`.
- [x] Do not accept any integration-test skips in the release check. Resolve environment failures rather than describing skipped tests as passing.
- [x] Verify clean data end to end: generate a small synthetic dataset, run `python -m bankflow run --input-dir data/samples --batch-id release-clean-001`, then inspect `python -m bankflow batch-status release-clean-001`.
- [x] Verify the defective-data workflow separately and check row counts/issues/quarantine in the database.
- [x] Run `git diff --check` and review the generated README commands for correctness.
- [x] Confirm `.env`, credentials, and generated CSV files are not tracked.
- [x] Update the README and setup guide so the delivered features are not described as future work.
- [x] Add the analytics SQL and CI workflow from this patch; run the CI workflow on GitHub and confirm it passes.
- [x] Create a pull request into `main` (PR #3 merged; PR #4 opened for CI test failure reporting & date dimension hotfix), review changed files, and merge only after the CI run is green. Avoid force pushes.
- [x] Refresh `PHASE_LOG.md` with exact commit IDs, test results, and verified CI runs; do not claim a hosted service or dashboard exists.

## Defer until after resume submission

- BI dashboard / Metabase / Power BI screenshots.
- Cloud scheduling, managed database, secrets management, and production monitoring.
- Larger sample datasets, additional analytics, and visual polish.
- Performance benchmarks beyond the acceptance tests.
