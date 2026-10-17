# BankFlow — Development Checklist and Phase Gates

> **Rule:** Work on one phase at a time. A phase is complete only when its exit criteria are verified, documentation is updated, a phase-log entry is recorded, and the requested GitHub handoff is attempted truthfully.

Status key: `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `VERIFIED`

Initial status for all implementation phases: **NOT STARTED**. Documentation preparation is not implementation completion.

## Phase 0 — Repository Baseline and Agent Alignment (Status: VERIFIED)

**Goal:** Make the project instructions and GitHub workflow reliable before code is written.

- [x] Inspect repository contents, current Git status, current branch, and remote URL.
- [x] Verify the expected GitHub remote is `https://github.com/GouravSharma26/BankFlow.git` or the equivalent HTTPS URL without `.git`.
- [x] Preserve the existing `plan.md`; do not regenerate or overwrite it unnecessarily.
- [x] Ensure all supporting docs are present and internally consistent.
- [x] Establish the initial baseline branch/commit if the repository has no code history.
- [x] Push the baseline to GitHub if credentials and permissions permit.
- [x] Record baseline commit, push status, and any permission blocker in `PHASE_LOG.md`.

**Exit criteria:** A clean repository baseline contains the plan and agent workflow docs, and the GitHub status is explicitly recorded. This phase does not mark application code complete.

## Phase 1 — Python Foundation, Synthetic Generator, and Staging (Status: VERIFIED)

**Goal:** Generate repeatable synthetic source files and ingest them into a PostgreSQL staging layer.

- [x] Finalize Python/package/dependency choices and document them.
- [x] Create `pyproject.toml`, source package, test layout, `.gitignore`, and `.env.example`.
- [x] Create safe local configuration and database connection handling.
- [x] Create source data contracts for customers, accounts, branches, and transactions.
- [x] Implement synthetic generator with fixed seed, configurable volume, dates, and defect scenarios.
- [x] Create database schema initialization for staging and batch metadata.
- [x] Implement file-level header/format checks and staging ingestion.
- [x] Capture source file, row number, batch ID, and ingest timestamp.
- [x] Add initial unit and database smoke tests.
- [x] Update setup instructions using verified commands.

**Exit criteria:** From a clean local setup, the developer can generate a small synthetic dataset, initialize the database, ingest it to staging, and inspect row/batch counts. At least one automated test verifies the path.

## Phase 2 — Validation, Quarantine, and Data Contracts (Status: VERIFIED)

**Goal:** Make accepted/rejected outcomes explicit and reproducible.

- [x] Implement stable validation rule codes.
- [x] Validate required fields, amount parsing, timestamps, supported values, currency, and references.
- [x] Distinguish file-level failures from row-level rejects.
- [x] Preserve source values needed to diagnose bad records.
- [x] Record issue severity, rule code, source row, batch, and useful reason.
- [x] Ensure malformed input does not disappear silently.
- [x] Add tests for each injected defect and expected disposition.
- [x] Update `docs/data_contract.md` and data dictionary.

**Exit criteria:** A mixed-quality dataset is processed deterministically; each tested defect produces the expected issue/outcome and the batch row accounting is explainable. (Verified: 46 automated tests pass with zero skips/failures against bankflow_test, including lifecycle guards, cross-batch reference restrictions, uniqueness, currency consistency, and duplicate historical exclusion. Phase 2 externally reviewed and approved at commit `d4e3c02`).


## Phase 3 — Warehouse Model, Loading, Idempotency, and Reconciliation (Status: VERIFIED / MERGED TO MAIN)

**Goal:** Load valid records to a dimensional PostgreSQL warehouse safely.

- [x] Create dimension tables for customer, account, branch, date, and transaction type as required by the plan.
- [x] Create `fact_transactions` with documented transaction grain and source lineage.
- [x] Define stable business-event identity and enforce uniqueness in PostgreSQL.
- [x] Load dimensions before facts and resolve dimension keys explicitly.
- [x] Use database transactions for logically related warehouse changes.
- [x] Implement replay-safe loading/upsert behavior and clear insert/update/skip counts.
- [x] Handle transaction statuses, reversals, currency, and late arrivals according to documented semantics.
- [x] Implement batch state transitions and machine-/human-readable summaries.
- [x] Implement count and, where comparable, value reconciliation.
- [x] Add integration and replay tests.

**Exit criteria:** A valid mixed batch populates the warehouse; the same event/file can be replayed without duplicate facts; a forced load failure does not leave an invalid partial warehouse state; reconciliation matches the defined contract. (Verified: Phase 3 dimensional warehouse loading, idempotency enforcement, replay protection, and reconciliation were reviewed, corrected for complete fact payload replay and concurrency, merged to main via PR #3 and PR #4, and verified in CI with 67 passing tests, zero failures, zero skips).

## Phase 4 — SQL Analytics and Metric Definitions (Status: VERIFIED)

**Goal:** Deliver reliable analytics whose definitions are documented and repeatable.

- [x] Implement daily activity query.
- [x] Implement deposit-versus-withdrawal query with explicit event/status semantics.
- [x] Implement branch/channel analysis.
- [x] Implement data-quality issue reports.
- [x] Implement ETL run/pipeline reports.
- [x] Create reporting views where useful.
- [x] Add indexes only when query use or measurements justify them.
- [x] Inspect relevant query plans and save reproducible examples where useful.
- [x] Document definitions, filters, currency rules, and known limitations.
- [x] Compare query output to expected fixture results.

**Exit criteria:** Required SQL reports run against known test data and return verified results; metric definitions prevent misleading totals. (Verified: Dedicated `reporting` schema created in `sql/05_reporting_views.sql` with 7 conformed analytical views; SQL report pack updated in `sql/04_analytics_queries.sql`; `docs/metric_definitions.md` updated from planned draft to verified contract; `docs/data_dictionary.md` updated with full view schemas; `bankflow report` CLI command implemented; 11 new PostgreSQL integration tests in `tests/test_analytics_integration.py` pass against known-answer fixtures; EXPLAIN query plans verified; full test suite passes with 78 tests, zero failures, zero skips against bankflow_test).

## Phase 5 — Dashboard Integration (Lovable Analytics Console)

**Goal:** Present the verified warehouse outputs in a simple, understandable dashboard via a secure, read-only API layer.
*Architecture Decision:* Selected existing purpose-built Lovable web console (`https://bankflow-analytics-console.lovable.app/`) rather than creating a second Power BI/Metabase dashboard; recorded in `docs/design_decisions.md` (TD-007, TD-020).

- [x] Tool Selection: Selected existing Lovable analytics web console, avoiding redundant dashboard tool proliferation.
- [x] Connect to the reporting layer using a dedicated read-only role: Created `sql/06_reporting_role.sql` (`bankflow_reporting_user`) granting `SELECT` exclusively on `reporting.*`.
- [x] Defense-in-depth API security: Application-level `readonly=True`, `autocommit=True`, and 5-second `statement_timeout` on all database sessions.
- [x] Build overview reporting endpoint: `GET /api/v1/overview` providing gross amounts, completed metrics, acceptance rates, date bounds, and batch counts isolated by currency.
- [x] Build transaction analysis endpoints: `GET /api/v1/daily`, `GET /api/v1/deposit-withdrawal`, `GET /api/v1/branch-channel`, `GET /api/v1/type-mix`, and paginated/filtered `GET /api/v1/transactions`.
- [x] Build pipeline/data-quality endpoints: `GET /api/v1/quality`, `GET /api/v1/batches`, and `GET /api/v1/quarantine`.
- [x] Add parameter validation & whitelisting: Strict validators for ISO currencies, statuses, channels, entities, severities, dispositions, date ranges (`YYYY-MM-DD`), sort column whitelist, and pagination bounds. Zero arbitrary SQL endpoints.
- [x] Label units, currencies, filters, and statuses clearly: Grouped currencies only (no cross-currency summation), gross positive event values, exact 2-decimal string serialization.
- [x] Verify API responses against direct reporting view SQL: 12 comprehensive PostgreSQL integration tests in `tests/test_api_integration.py` verify 1-to-1 parity between API metrics and reporting views.
- [x] Document dashboard integration contract: Created `docs/dashboard_api_contract.md` defining endpoints, schemas, CORS, local development, `VITE_BANKFLOW_API_BASE_URL`, and the hosted demo-mode boundary.
- [x] Add CLI serve command: Implemented `bankflow serve [--host] [--port] [--reload] [--test-db]`.

**Exit criteria:** Dashboard reporting API data matches authoritative PostgreSQL reporting views for all test cases, enforces read-only access and strict input validation without leaking credentials, and frontend integration contract is fully documented. (Verified: 12/12 API integration tests pass, full suite 90/90 tests pass with zero failures and zero skips).

## Phase 5.1 — Hotfix: API Review Findings & Hardening

**Goal:** Address five verified code-review findings from the Phase 5 merge before proceeding to Phase 6.

- [x] **Finding 1 (CLI Configuration Precedence):** Updated `bankflow serve` to resolve `ApiConfig` via `ApiConfig.from_env()`, honouring `BANKFLOW_REPORTING_DB_USER` and `BANKFLOW_REPORTING_DB_PASSWORD` alongside CLI host/port overrides. Added 6 regression tests in `tests/test_api_config.py`.
- [x] **Finding 2 (Hardcoded Credential Removal):** Removed static password `'reporting_password_placeholder'` from `sql/06_reporting_role.sql`. Documented secure, out-of-band password setup via interactive `\password` and psql `-v REPORTING_PW=...` in `.env.example`, `HUMAN_SETUP.md`, and `docs/dashboard_api_contract.md`.
- [x] **Finding 3 (Canonical Quality Dispositions):** Aligned API quality disposition validation with canonical constants `ACCEPTED`, `REJECTED`, `WARNED`, and `SKIPPED` across `validators.py`, `schemas.py`, `routes/quality.py`, and documentation.
- [x] **Finding 4 (Overview Entity Distinct Totals):** Corrected `active_accounts` and `active_customers` in `GET /api/v1/overview` so they represent true period-wide distinct entities from `reporting.v_transaction_details`, rather than single-day `MAX()`. Added multi-day, same-currency regression fixture verifying distinct union count.
- [x] **Finding 5 (Strict Date & Currency Validation):** Replaced permissive date parsing with strict `parse_strict_date` requiring exact `YYYY-MM-DD` syntax and calendar bounds, rejecting compact dates, ISO week dates, whitespace padding, and invalid calendar days. Enforced supported currencies (`USD`, `EUR`, `GBP`). Added 38 regression tests in `tests/test_api_validators.py` and `tests/test_api_integration.py`.

**Exit criteria:** Zero failures and zero skips across full test suite with mandatory PostgreSQL integration tests; clean `git diff --check`; no credentials or secrets committed; PR opened for review without auto-merging.

## Phase 6 — Hardening, CI, Documentation, and Portfolio Release

**Goal:** Make the project easy to test, review, reproduce, and explain.

- [ ] Complete unit, PostgreSQL integration, end-to-end, and relevant failure-injection tests.
- [ ] Ensure the test database is separate and the test runner guards against unsafe targets.
- [ ] Add GitHub Actions workflow for tests and any configured lint/format checks.
- [ ] Verify configuration and secret-handling hygiene.
- [ ] Run `git diff --check` and inspect all tracked changes.
- [ ] Verify clean-clone installation and run instructions.
- [ ] Finalize README, architecture, data contract/dictionary, testing, and decision documentation.
- [ ] Measure actual runtime on a documented dataset only if reporting performance.
- [ ] Record known limitations, setup requirements, and optional extensions.
- [ ] Prepare interview explanation and reproducible demo.

**Exit criteria:** A reviewer can follow the repository instructions to generate synthetic data, run the ETL, inspect rejects and warehouse output, reproduce SQL reports, run tests, and understand limitations without undocumented manual steps.

## Phase Completion Template

Copy this block into `PHASE_LOG.md` after each phase:

```markdown
### Phase N — <name>
- Status: VERIFIED / BLOCKED
- Date:
- Commit:
- Branch:
- GitHub push: pushed / blocked (reason)
- Scope delivered:
- Verification commands:
- Test results:
- Acceptance evidence:
- Known limitations:
- Reviewer findings:
- Follow-up items:
```

## Global Rules

- Do not start Phase N+1 until Phase N's acceptance criteria have passed or the user explicitly approves proceeding with a documented exception.
- Do not claim an untested metric, performance gain, or feature.
- Do not commit real financial/customer data, secrets, `.env`, database dumps, virtual environments, or large generated files.
- Every feature must have appropriate tests and matching documentation.
