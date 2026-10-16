# BankFlow — Phase Log and Review Record

> Append-only project history. Record verified outcomes, not intentions. Do not mark work completed until the acceptance evidence is available.

## Current Status

- Overall status: `VERIFIED LOCALLY (Phase 3 Completed — Push & Review Pending)`
- Current phase: `Phase 3 — Warehouse Model, Loading, Idempotency, and Reconciliation`
- Last verified implementation phase: `Phase 3 — Warehouse Model, Loading, Idempotency, and Reconciliation`
- GitHub repository: <https://github.com/GouravSharma26/BankFlow>
- Baseline commit: `cc2b371`
- Latest reviewed commit: `d51e4e3`
- Implementation commit: `3b5b262`

## How to Maintain This File

For every phase, add a new entry below the template. Keep earlier entries as historical evidence; correct factual errors with a dated note rather than quietly rewriting the history. Record the exact commit SHA, branch, push status, commands, test counts, and reviewer findings.

## Phase Entries

### Planning Documentation Prepared

- Status: `DOCUMENTATION PREPARED — IMPLEMENTATION NOT STARTED`
- Date: `2026-10-16`
- Scope: Master plan and agent/developer workflow documentation prepared for review and placement in the repository.
- Implementation verification: `Not applicable; no application code is claimed by this entry.`
- GitHub push: `Not verified; this local documentation package has not been confirmed on GitHub.`
- Next action: Verify the local folder and remote, commit/push the documentation baseline, then execute Phase 0/Phase 1 according to `DEVELOPMENT_CHECKLIST.md`.

### Phase 0 — Repository Baseline and Agent Alignment

- Status: VERIFIED
- Date: 2026-10-16
- Branch: main
- Commit SHA: b863ee1 (Baseline push) / 1757c94 (Phase log update)
- GitHub URL: <https://github.com/GouravSharma26/BankFlow/commit/1757c94>
- Push status: Pushed successfully to `origin/main` and `origin/phase/0-repo-baseline`
- Objective: Verify repository structure, documents, Git configuration, establish the clean documentation baseline on GitHub, and align with agent operating guidelines before starting application code.
- Changes delivered:
  - Validated all 15 required planning, documentation, and agent workflow files.
  - Preserved `plan.md` as canonical specification without regression.
  - Initialized Git repository with default branch `main`.
  - Configured remote `origin` to `https://github.com/GouravSharma26/BankFlow.git`.
  - Verified Git identity (`GouravSharma26` / `gourav123sharma4567@gmail.com`).
  - Verified local environment tool versions (Git 2.46.0, Python 3.12.6, pip 25.0.1, PostgreSQL 17.4).
  - Pushed initial documentation baseline commit `b863ee1` to GitHub `main`.
- Tests/commands executed:
  - `git ls-remote https://github.com/GouravSharma26/BankFlow.git` (verified empty remote ready for push)
  - `git init -b main`
  - `git remote add origin https://github.com/GouravSharma26/BankFlow.git`
  - `git config user.name; git config user.email`
  - `git --version; python --version; python -m pip --version; psql --version`
  - `git add AGENTS.md ANTIGRAVITY_START_HERE.md DEVELOPMENT_CHECKLIST.md HUMAN_SETUP.md PHASE_LOG.md README.md REVIEW_WORKFLOW.md plan.md docs/`
  - `git commit -m "docs(baseline): establish project specification and agent workflow"`
  - `git push -u origin main`
- Test outcomes: All pre-flight checks and Git commands succeeded with exit code 0.
- Acceptance evidence: Baseline commit `b863ee1` is pushed and visible on GitHub `main` at `https://github.com/GouravSharma26/BankFlow/tree/main`.
- Review findings: None (baseline phase).
- Fixes or accepted risks: None.
- Known limitations: Application implementation has not started yet (Phase 1 will begin the application skeleton and synthetic generator).
- Next action: Handoff Phase 0 for review; next phase is Phase 1 — Python Foundation, Synthetic Generator, and Staging.

### Phase 1 — Python Foundation, Synthetic Generator, and Staging

- Status: VERIFIED
- Date: 2026-10-16
- Branch: phase/1-foundation
- Commit SHA: 76d68ef
- GitHub URL: <https://github.com/GouravSharma26/BankFlow/tree/phase/1-foundation>
- Push status: Pushed to `origin/phase/1-foundation`
- Objective: Set up Python packaging, safe configuration, deterministic synthetic generator, PostgreSQL staging and monitoring schemas, file-level CSV header checks, staging ingestion, unit tests, and setup instructions.
- Changes delivered:
  - Created `.gitignore` ignoring `.env`, caches, virtualenvs, local databases, and generated datasets (`data/**/*.csv`).
  - Created `.env.example` with discrete and URL connection variables, safe test database guardrails, and placeholders.
  - Created `pyproject.toml` declaring dependencies (`psycopg2-binary`, `python-dotenv`, `click`, optional `pytest`) and entry point `bankflow`.
  - Implemented `src/bankflow/constants.py` with canonical domain values, quality rule codes, and column contracts.
  - Implemented `src/bankflow/config.py` with environment parsing, test database safety assertions (`is_test_database`, `assert_safe_for_reset`).
  - Implemented `src/bankflow/db.py` with connection and transaction context managers (`get_connection`, `transaction`, `check_connection`).
  - Implemented `src/bankflow/generator/defects.py` with configurable defect injection policies (`DefectConfig`).
  - Implemented `src/bankflow/generator/generator.py` with deterministic `random.Random(seed)` generator for branches, customers, accounts, and transactions using `Decimal` for amounts and synthetic opaque IDs.
  - Implemented `sql/01_staging_schema.sql` and `src/bankflow/staging/schema.py` creating `monitoring` and `staging` tables (`stg_branches`, `stg_customers`, `stg_accounts`, `stg_transactions`, `etl_batch_runs`).
  - Implemented `src/bankflow/staging/loader.py` validating file headers, registering batch runs, capturing source file, row number, batch ID, ingestion timestamp, and raw payload.
  - Implemented `src/bankflow/__main__.py` with CLI commands: `init-db`, `test-connection`, `generate`, `stage`, `batch-status`.
  - Created automated test suite: 14 unit tests passed covering config guards, deterministic generation, defect injection, CSV export, and file header validation; 1 integration test configured for PostgreSQL test DB.
  - Added `docker-compose.yml` and `docker/01-init-test-db.sql` providing one-command local PostgreSQL 17 setup with both `bankflow` and `bankflow_test` databases.
  - Updated `docs/design_decisions.md` (TD-008 accepted psycopg2-binary, TD-010 accepted Docker Compose), `docs/data_dictionary.md` (populated staging/monitoring schemas), and `HUMAN_SETUP.md` (verified execution and docker compose commands).
  - Cleaned minor Phase 0 trailing whitespace in `plan.md`.
- Tests/commands executed:
  - `docker compose up -d` (PostgreSQL 17 container started and healthy on 127.0.0.1:5433)
  - `python -m pytest tests -v` (22 passed, 0 skipped, 0 failed with live PostgreSQL container)
  - `pip install -e ".[dev]"` (installed bankflow 0.1.0 with pytest)
  - `bankflow --help` (verified CLI options)
  - `bankflow generate --output-dir data/samples --seed 42 --transactions 100` (generated 4 clean CSV files)
  - `bankflow test-connection; bankflow test-connection --test-db` (verified connectivity to primary and test DBs)
  - `bankflow init-db` (initialized staging and monitoring schemas)
  - `bankflow stage --input-dir data/samples` (ingested 170 records into staging tables)
  - `bankflow batch-status <batch_id>` (verified batch state and record count audit)
  - `git diff --check` (clean, 0 whitespace errors)
- Test outcomes: 22 passed, 0 skipped, 0 failed.
- Acceptance evidence: Developer can launch local PostgreSQL with `docker compose up -d` restricted to 127.0.0.1 loopback, generate synthetic datasets with date ranges, initialize staging schema, ingest staging data, inspect batch records, and run all 22 automated tests covering header validation, empty dataset contracts, duplicate defect scenarios, explicit batch registration, and failed-batch accounting.
- Review findings: Phase 1 code review identified: loopback port binding requirement, HUMAN_SETUP.md step ordering and -v volume deletion precautions, staging header validation (extra/duplicate columns), empty-file contract (0 data rows vs 0 bytes), explicit batch-ID registration, test-database safety checks, failed-batch accounting, duplicate defect generation edge condition (idx=0), date-range validation, integration-test skip reporting, and URL config test completeness.
- Fixes or accepted risks:
  - Restricted Docker Compose port publishing to `127.0.0.1:${BANKFLOW_DB_PORT:-5432}:5432`.
  - Reordered HUMAN_SETUP.md to configure `.env` before `docker compose up -d` and added warning against `docker compose down -v`.
  - Added `RULE_FILE_HEADER_MISMATCH` and enforced strict header checks (detecting duplicate and unexpected extra columns).
  - Enforced empty-file contract: both 0-byte files and headers-only datasets trigger `RULE_FILE_EMPTY`.
  - Guaranteed `batch_id` registration in `monitoring.etl_batch_runs` whether auto-generated or explicitly supplied.
  - Implemented accurate `records_extracted` and `records_staged` accounting in `update_batch_failure`.
  - Fixed duplicate defect generation in `_inject_defects` to properly duplicate IDs even when `missing_txn_id_count == 0`.
  - Added start/end date validation (`end_date >= start_date`) and added late-arriving event defect (scenario 15).
  - Enhanced integration test skip message with exact connection error, and configured fail on CI / required runs.
  - Rewrote URL config test with direct assertions on constructor, `from_url`, and `from_env`.
- Known limitations: Dimensional warehouse loading and Phase 2 validation system are intentionally deferred to Phase 2 and Phase 3.
- Next action: Submit Phase 1 review fixes for final approval; next phase is Phase 2 — Validation, Quarantine, and Data Contracts.

### Phase 1 — Review Fixes (Database Guard, Header Contract, Date Ranges, Batch Collision)

- Status: VERIFIED
- Date: 2026-10-16
- Branch: phase/1-foundation
- Commit SHA: 7974ae4
- GitHub URL: <https://github.com/GouravSharma26/BankFlow/commit/7974ae4>
- Push status: Pushed to origin/phase/1-foundation
- Objective: Resolve all remaining Phase 1 review findings from commit `67db1fd`:
  1. Strengthen test-database guard with strict token-boundary matching and forbidden production tokens (`production`, `prod`, `live`, `backup`, `master`, `main`, `real`, `postgres`), rejecting production-like names (`latest`, `contest`, `production_test_backup`, `prod_test`, `master_test`) while preserving valid test names (`bankflow_test`, `test_db`, `ci_test_warehouse`).
  2. Prevent CSV header normalization from corrupting staging data by strictly rejecting headers with leading/trailing whitespace, unexpected columns, reordered columns, and duplicate columns; and binding `csv.DictReader` explicitly to canonical `fieldnames=expected_columns` after skipping verified headers, ensuring populated transaction IDs can never silently become NULL.
  3. Correct duplicate-ID defect generation in standard defect configuration to inject both a missing transaction ID and a separate duplicate of a valid, non-empty ID (sourced from an unaffected row).
  4. Complete date-range support with `--start-date` and `--end-date` options in CLI and generator, defining the end date as inclusive across the full calendar day in UTC (23:59:59).
  5. Enforce explicit batch-ID collision behavior, verifying that attempting to reuse an existing batch ID raises `RULE_BATCH_ALREADY_EXISTS` without modifying the original batch run record in `monitoring.etl_batch_runs` or duplicating staged rows in `staging.stg_*`, and returns a useful error to the CLI caller.
  6. Correct stale documentation in `README.md` and `HUMAN_SETUP.md` to reflect implemented Phase 1 and current PostgreSQL setup, explicitly marking the validation engine, dimensional warehouse, analytics, and dashboard as future work.
- Changes delivered:
  - `src/bankflow/config.py`: Implemented regex tokenization `re.split(r"[^a-zA-Z0-9]+", name)` and forbidden production keyword rejection list.
  - `src/bankflow/constants.py`: Added `RULE_BATCH_ALREADY_EXISTS = "BATCH_ALREADY_EXISTS"`.
  - `src/bankflow/generator/generator.py`: Defined UTC end date inclusive across 23:59:59; sourced duplicate transaction ID from an unaffected row (`txns[-1]`) in standard defect config.
  - `src/bankflow/staging/loader.py`: Enforced strict header whitespace rejection and column ordering checks; bound DictReader to canonical columns; guarded batch registration against collision mutation.
  - `src/bankflow/__main__.py`: Added `--start-date` and `--end-date` options with ISO format and order validation; formatted batch collision CLI error message.
  - `tests/test_config.py`: Added regression test coverage for accepted names (`bankflow_test`, `test_db`, `ci_test_warehouse`, `bankflow-test`, `test`) and rejected names (`latest`, `contest`, `attest`, `detest_db`, `greatest_app`, `production_test_backup`, `prod_test`, `test_live`, `test_backup`, `master_test`, `main_test_db`, `bankflow`, `postgres`, `production_warehouse`, `""`).
  - `tests/test_generator.py`: Verified standard defect configuration contains both missing transaction ID and duplicate of valid non-empty transaction ID; tested inclusive date boundaries (23:59:59 UTC) and CLI date range argument parsing and validation.
  - `tests/test_staging_validation.py`: Added tests for header whitespace rejection, column ordering mismatch rejection, and proof that populated transaction IDs cannot become NULL.
  - `tests/test_db_integration.py`: Added `test_batch_id_collision_preserves_original_state` ensuring second run is rejected with `RULE_BATCH_ALREADY_EXISTS`, original monitoring batch run remains `SUCCEEDED` with original counts, staged rows are not duplicated, and CLI output informs the caller.
  - `README.md` & `HUMAN_SETUP.md`: Reflected Phase 1 implementation status, actual repository layout, CLI commands, and marked future phases.
- Tests/commands executed:
  - `python -m pytest tests -v` (28 passed, 0 skipped, 0 failed in 19s against live `bankflow_test` PostgreSQL instance)
  - `python -m bankflow test-connection; python -m bankflow test-connection --test-db`
  - `git diff --check` (clean, 0 whitespace errors)
- Test outcomes: 28 passed, 0 skipped, 0 failed.
- Acceptance evidence: All 6 review requirements verified with regression tests; integration tests executed against PostgreSQL container on 127.0.0.1:5433; git diff clean with no secrets or extraneous files.
- Review findings: All remaining findings from commit `67db1fd` resolved.
- Fixes or accepted risks: None.
- Known limitations: Phase 2 validation and quarantine engine, Phase 3 dimensional warehouse, Phase 4 analytics, and Phase 5 dashboard are planned future phases.
- Next action: Submit Phase 1 review fixes for final review.

### Phase 1 — Review Fix (Raw Staging Preservation and Surplus Fields)

- Status: VERIFIED
- Date: 2026-10-16
- Branch: phase/1-foundation
- Commit SHA: a1b1660
- GitHub URL: <https://github.com/GouravSharma26/BankFlow/commit/a1b1660>
- Push status: Pushed to origin/phase/1-foundation
- Objective: Fix raw staging-data preservation and surplus fields handling:
  1. In `src/bankflow/staging/loader.py`, ensure ingestion methods for branches, customers, accounts, and transactions preserve original source field values in staging without trimming leading/trailing whitespace or otherwise normalizing them.
  2. Preserve original row representation in `raw_payload`, including leading/trailing whitespace and any surplus CSV fields beyond the declared header schema under `raw_payload['_surplus']`.
  3. Keep source-field normalization and defect detection in the validation layer; do not mix it into raw ingestion.
  4. Retain strict header validation.
  5. Add PostgreSQL integration test `test_raw_staging_preservation_and_surplus_fields` inspecting persisted values (transaction ID with whitespace, amount with whitespace, row with surplus values, ensuring no values disappear silently).
  6. Update data contract and data dictionary to document raw staging preservation and surplus field policy.
- Changes delivered:
  - `src/bankflow/staging/loader.py`: Removed whitespace `.strip()` in `ingest_branches`, `ingest_customers`, `ingest_accounts`, and `ingest_transactions`; configured `csv.DictReader(..., restkey="_surplus")` and preserved surplus fields under `_surplus` in `raw_payload`.
  - `tests/test_db_integration.py`: Added `test_raw_staging_preservation_and_surplus_fields` verifying PostgreSQL staging columns and JSONB `raw_payload` retain whitespace and surplus values.
  - `docs/data_contract.md`: Documented Raw Staging Preservation and Surplus Fields Policy in Section 6.
  - `docs/data_dictionary.md`: Documented exact string preservation and `_surplus` array in `raw_payload` under Staging section.
- Tests/commands executed:
  - `python -m pytest tests -v` (29 passed, 0 skipped, 0 failed in 23s against live `bankflow_test` PostgreSQL instance)
  - `git diff --check`
- Test outcomes: 29 passed, 0 skipped, 0 failed.
- Acceptance evidence: Staging integration test proves whitespace in transaction IDs and amounts is preserved in PostgreSQL staging tables, surplus fields are captured under `_surplus` in `raw_payload`, and no values disappear.
- Review findings: Resolved source preservation and surplus field finding from commit `4f63c0d`.
- Fixes or accepted risks: None.
- Known limitations: Phase 2 validation and quarantine engine, Phase 3 dimensional warehouse, Phase 4 analytics, and Phase 5 dashboard are planned future phases.
- Next action: Submit Phase 1 review fixes for final review.

### Phase 2 — Validation, Quarantine, and Data Contracts

- Status: CHANGES REQUESTED (Review on 0f551a7)
- Date: 2026-10-16
- Branch: phase/2-validation-quarantine
- Commit SHA: 0f551a7
- GitHub URL: <https://github.com/GouravSharma26/BankFlow/commit/0f551a7>
- Push status: Pushed to origin/phase/2-validation-quarantine
- Objective: Build a deterministic validation engine that processes staged source records, assigns stable rule codes, quarantines invalid records, and accounts for the disposition of every processed row while preserving raw staging data without in-place mutation.
- Changes delivered:
  - Database Schema (`sql/02_validation_quarantine_schema.sql` and `src/bankflow/validation/schema.py`):
    - `monitoring.data_quality_issues`: tracks issue ID, batch ID, entity type, source row ID/number, filename, stable rule code, severity (ERROR, WARNING, INFO), reason, and disposition with foreign keys and performance indexes.
    - `quarantine.quarantined_records`: captures quarantine ID, batch ID, entity type, source row ID, primary rule code, issue count, and timestamp. References staging row without duplicating raw data.
    - `quarantine.vw_quarantined_transactions`: relational view joining quarantine with `staging.stg_transactions` for instant diagnostic queryability.
  - Data Models (`src/bankflow/validation/models.py`):
    - `ValidationIssue`: typed representation with DB tuple serialization.
    - `RowValidationOutcome`: properties `is_rejected`, `has_warnings`, and `disposition`.
    - `BatchValidationSummary`: accounts for `records_evaluated`, `records_valid`, `records_rejected`, `records_warned`, `records_skipped`, and `total_issues_count`.
  - Validation Engine (`src/bankflow/validation/validator.py`):
    - Validates entities in relational reference order (`branches` -> `customers` -> `accounts` -> `transactions`).
    - Enforces stable rule codes: `TXN_ID_MISSING`, `TXN_ID_DUPLICATE`, `ACCOUNT_ID_MISSING`, `ACCOUNT_NOT_FOUND`, `AMOUNT_MISSING`, `AMOUNT_PARSE_ERROR`, `AMOUNT_RULE_VIOLATION`, `TIMESTAMP_PARSE_ERROR`, `TYPE_UNSUPPORTED`, `STATUS_UNSUPPORTED`, `CHANNEL_UNSUPPORTED`, `CURRENCY_MISSING`, `CURRENCY_UNSUPPORTED`, etc.
    - Uses Python `Decimal` for amount validation, rejecting non-finite values (NaN/Inf) and enforcing `> 0.00`.
    - Uses ISO 8601 with explicit timezone-aware parsing for timestamps.
    - Preserves late-arriving past events as valid events per explicit documented policy.
    - Records all detectable issues per row without inflating `records_rejected` (1 row with N issues = 1 rejected row).
    - Guarantees validation idempotency: clears existing batch issues/quarantine before re-evaluation within a database transaction.
    - Updates `monitoring.etl_batch_runs` with `records_valid`, `records_rejected`, and status (`SUCCEEDED` or `SUCCEEDED_WITH_REJECTIONS`).
  - CLI Integration (`src/bankflow/__main__.py`):
    - Added `bankflow validate <batch_id> [--test-db]`.
    - Enhanced `bankflow stage` with `--validate` flag for immediate validation.
    - Updated `bankflow batch-status` to report `records_valid`, `records_rejected`, and total quality issues.
  - Test Suite (`tests/test_validation.py` and `tests/test_validation_integration.py`):
    - Unit tests: single/multi-issue row outcomes, accounting invariants, amount Decimal checks, timestamp timezone parsing, and individual rule tests for branches, customers, accounts, transactions.
    - Live PostgreSQL integration tests against `bankflow_test`: clean batch validation (0 rejections), defective batch quarantine with exact rule codes, validation idempotency, view verification, and CLI invocation.
  - Documentation:
    - Updated `docs/data_quality_rules.md`, `docs/data_contract.md`, `docs/data_dictionary.md`, `docs/architecture.md`, and `docs/design_decisions.md` (TD-016 and TD-017).
- Tests/commands executed:
  - `python -m pytest tests -v` (39 passed, 0 skipped, 0 failed in 56s against live PostgreSQL `bankflow_test`)
  - `git diff --check`
- Test outcomes: 39 passed, 0 skipped, 0 failed.
- Acceptance evidence:
  - 39 automated tests pass with 0 skips against dedicated PostgreSQL `bankflow_test`.
  - Batch accounting invariant `records_evaluated = records_valid + records_rejected` verified on clean and defective datasets.
  - Quarantined records verified joinable via `quarantine.vw_quarantined_transactions` with raw staging payloads preserved intact.
  - Re-running validation on the same batch produces identical counts without duplicate records.
- Review findings: Review returned CHANGES REQUESTED on commit `0f551a7` with 6 specific findings:
  1. Protect batch lifecycle state: reject validation of FAILED, RUNNING, PENDING, or ineligible batches using FOR UPDATE locks within the validation transaction; preserve original error_summary and accounting.
  2. Restrict cross-batch reference resolution: require prior references to come from completed, successfully validated batches (`validated_at IS NOT NULL`), excluding unvalidated, failed, or quarantined rows.
  3. Complete required-field and date validation: add validation for `branch_name`, `region`, `created_date`, `opened_date`, `source_system`, enforcing ISO `YYYY-MM-DD` without default fallbacks.
  4. Validate entity identifier uniqueness: add stable duplicate rules (`BRANCH_ID_DUPLICATE`, `CUSTOMER_ID_DUPLICATE`, `ACCOUNT_ID_DUPLICATE`), quarantine all duplicate occurrences, and exclude duplicate accounts from the trusted cache so referencing transactions fail.
  5. Define currency consistency: enforce that transactions must match their referenced account currency, rejecting mismatches under `CURRENCY_MISMATCH`.
  6. Correct project records: update `PHASE_LOG.md` with corrective review entry and update data contract and data dictionary documentation.
- Fixes or accepted risks: All 6 findings addressed in corrective review commit.
- Known limitations: Dimensional warehouse loading deferred to Phase 3.
- Next action: Implement all requested corrections and verify test suite.

### Phase 2 — Final Review Corrections

- Status: VERIFIED
- Date: 2026-10-16
- Branch: phase/2-validation-quarantine
- Commit SHA: 521947a (Phase 2 review corrections)
- GitHub URL: <https://github.com/GouravSharma26/BankFlow/tree/phase/2-validation-quarantine>
- Push status: Ready for push
- Objective: Resolve all 6 Phase 2 review findings on branch `phase/2-validation-quarantine` based on commit `0f551a7`:
  1. Protect batch lifecycle state: validate_batch() locks the batch row with `SELECT ... FOR UPDATE` within the transaction, rejecting batches in `FAILED`, `RUNNING`, `PENDING`, or ineligible states with explicit errors. It preserves original status, error summary, and counts completely untouched. Legitimate revalidation of previously validated batches remains fully supported. Added live PostgreSQL integration test `test_validation_lifecycle_guard_rejects_failed_batch`.
  2. Restrict cross-batch reference resolution: `_validate_branches()`, `_validate_customers()`, and `_validate_accounts()` restrict prior reference resolution to batches with a completed validation outcome (`validated_at IS NOT NULL`, `status IN ('SUCCEEDED', 'SUCCEEDED_WITH_REJECTIONS')`, and `records_valid + records_rejected == records_staged`). Rows in unvalidated, failed, running, or incomplete batches, as well as quarantined rows, are strictly excluded. Added live PostgreSQL integration test `test_cross_batch_reference_resolution_restrictions`.
  3. Complete required-field and date validation: added stable rule codes and validation for missing or whitespace-only required values: `BRANCH_NAME_MISSING`, `BRANCH_REGION_MISSING`, `SOURCE_SYSTEM_MISSING`. Added date validation enforcing ISO 8601 calendar date format `YYYY-MM-DD` for customer `created_date` and account `opened_date` under `DATE_PARSE_ERROR` without substituting default dates.
  4. Validate entity identifier uniqueness: added stable duplicate rules: `BRANCH_ID_DUPLICATE`, `CUSTOMER_ID_DUPLICATE`, `ACCOUNT_ID_DUPLICATE`. Ambiguous duplicates are quarantined. Duplicate or quarantined accounts are excluded from `valid_accounts`, causing transactions referencing them to be rejected under `ACCOUNT_NOT_FOUND`. Added unit and PostgreSQL integration coverage.
  5. Define currency consistency: implemented `RULE_CURRENCY_MISMATCH` ("CURRENCY_MISMATCH"). Transactions whose currency differs from their referenced account currency are rejected. Updated `docs/data_quality_rules.md` and `docs/data_contract.md`. Added unit and integration tests.
  6. Correct project records: updated `PHASE_LOG.md` preserving historical evidence of commit `0f551a7` and adding this corrective review entry. Updated `docs/data_dictionary.md` to document the new `validated_at TIMESTAMPTZ` column on `monitoring.etl_batch_runs`. Updated `DEVELOPMENT_CHECKLIST.md`.
- Changes delivered:
  - `src/bankflow/constants.py`: Added 8 new rule codes (`BRANCH_NAME_MISSING`, `BRANCH_REGION_MISSING`, `BRANCH_ID_DUPLICATE`, `CUSTOMER_ID_DUPLICATE`, `ACCOUNT_ID_DUPLICATE`, `DATE_PARSE_ERROR`, `SOURCE_SYSTEM_MISSING`, `CURRENCY_MISMATCH`).
  - `sql/02_validation_quarantine_schema.sql` and `src/bankflow/validation/schema.py`: Added `validated_at TIMESTAMPTZ` column and `idx_batch_validated` index to `monitoring.etl_batch_runs`.
  - `src/bankflow/validation/validator.py`: Added batch lifecycle state row locking (`FOR UPDATE`), lifecycle validation guards, completed validation query filters for cross-batch references, required field checks, ISO date checks, entity duplicate detection, and transaction-account currency matching.
  - `tests/test_validation.py`: Updated unit tests for duplicate entities, missing required fields, date parse errors, transaction-account currency mismatches, and `valid_accounts` dict structure.
  - `tests/test_validation_integration.py`: Added 3 live PostgreSQL integration tests verifying batch lifecycle guards, cross-batch reference restrictions, entity duplicates, and currency mismatch.
  - `docs/data_quality_rules.md`, `docs/data_contract.md`, `docs/data_dictionary.md`, `DEVELOPMENT_CHECKLIST.md`, `PHASE_LOG.md`.
- Tests/commands executed:
  - `python -m pytest tests -v` (42 passed, 0 skipped, 0 failed in 75s against live `bankflow_test` PostgreSQL instance)
  - `git diff --check`
- Test outcomes: 42 passed, 0 skipped, 0 failed.
- Acceptance evidence:
  - 42 tests passing with 0 skips across the entire test suite.
  - Integration test `test_validation_lifecycle_guard_rejects_failed_batch` proves FAILED and RUNNING batches are refused with zero alterations to status, error summary, or staging counts.
  - Integration test `test_cross_batch_reference_resolution_restrictions` proves transactions referencing accounts in unvalidated or failed batches receive `ACCOUNT_NOT_FOUND`, while referencing previously validated accounts succeeds.
  - Integration test `test_duplicate_entities_and_currency_mismatch_integration` proves duplicate entities are quarantined, duplicate accounts cannot be resolved by transactions, and currency mismatch triggers `CURRENCY_MISMATCH`.
- Review findings: All 6 review findings resolved.
- Fixes or accepted risks: None.
- Known limitations: Phase 3 dimensional warehouse (`dim_*`, `fact_transactions`), warehouse loading, idempotency/replay against fact tables, and analytics reports are Phase 3/4 scope.
- Next action: Submit Phase 2 review corrections for approval; wait for external review before starting Phase 3.

### Phase 2 — Final Data-Integrity Fixes (Current-Batch Duplicate Exclusion and Strict Dates)

- Status: VERIFIED LOCALLY — EXTERNAL REVIEW APPROVAL PENDING
- Date: 2026-10-16
- Branch: phase/2-validation-quarantine
- Commit SHA: 5e94dfc (Implementation) / d51e4e3 (Documentation)
- GitHub URL: <https://github.com/GouravSharma26/BankFlow/tree/phase/2-validation-quarantine>
- Push status: Pushed to origin/phase/2-validation-quarantine
- Objective: Resolve the two remaining Phase 2 review findings without rebuilding working components or starting Phase 3:
  1. Finding 1: Prevent ambiguous current-batch IDs from being restored by historical references. Retain the set of duplicate branch IDs, customer IDs, and account IDs detected in the current batch and exclude them when constructing trusted reference sets from previously validated batches. Ensure duplicate accounts cannot be restored into `valid_accounts`, causing referencing transactions to be rejected under `ACCOUNT_NOT_FOUND`. Apply consistent logic to branches and customers while preserving unrelated valid historical entities.
  2. Finding 2: Enforce strict YYYY-MM-DD calendar-date formatting with a reusable strict date parser. Require exact `YYYY-MM-DD` syntax and calendar validation, never supply a default/fallback date, and return a consistent validation outcome using `RULE_DATE_PARSE_ERROR` ("DATE_PARSE_ERROR"). Use it for customer `created_date` and account `opened_date`.
- Changes delivered:
  - `src/bankflow/validation/dates.py`: Created reusable parser `parse_strict_date(value)` returning `StrictDateResult(is_valid, parsed_date, error_message)`. Enforces regex `^\d{4}-\d{2}-\d{2}$` without whitespace, validates calendar validity via `datetime.strptime(..., "%Y-%m-%d").date()` (rejecting leap days in non-leap years, day 30 in February, invalid months, etc.), rejects week dates (`2026-W03-4`) and compact dates (`20260115`), and never substitutes defaults.
  - `src/bankflow/validation/validator.py`:
    - Updated `_validate_branches()`, `_validate_customers()`, and `_validate_accounts()` to retain `duplicate_b_ids`, `duplicate_c_ids`, and `duplicate_a_ids` and exclude them when querying and loading trusted historical references from previously validated batches.
    - Updated customer `created_date` and account `opened_date` validation to use `parse_strict_date` directly, mapping missing, empty, whitespace-only, malformed, non-calendar, and non-conforming dates to `RULE_DATE_PARSE_ERROR`.
  - `src/bankflow/validation/__init__.py`: Exported `parse_strict_date` and `StrictDateResult`.
  - `tests/test_validation.py`: Added `test_strict_date_parser` and `test_duplicate_identifiers_not_restored_from_historical_lookups`.
  - `tests/test_validation_integration.py`: Added live PostgreSQL integration tests `test_historical_account_duplicated_in_current_batch_cannot_be_restored` and `test_strict_date_validation_integration`.
  - `DEVELOPMENT_CHECKLIST.md` & `PHASE_LOG.md`: Updated to record 46 passed tests and reflect that external review approval is pending.
- Tests/commands executed:
  - `python -m pytest tests -v` (46 passed, 0 skipped, 0 failed in 118s against live `bankflow_test` PostgreSQL instance)
  - `git diff --check` (clean, 0 errors)
- Test outcomes: 46 passed, 0 skipped, 0 failed.
- Acceptance evidence:
  - Integration test `test_historical_account_duplicated_in_current_batch_cannot_be_restored` proves that an account duplicated in the current batch is not restored into `valid_accounts` despite existing in a previous validated batch, causing referencing transactions to be rejected under `ACCOUNT_NOT_FOUND`, while non-duplicated historical accounts resolve successfully.
  - Integration test `test_strict_date_validation_integration` proves that `2026-01-15` is accepted, while `20260115`, `2026-W03-4`, `2026-02-30`, `""`, `"   "`, and malformed inputs are quarantined with `RULE_DATE_PARSE_ERROR`.
  - Unit tests verify parser rejects defaults and validates leap years correctly.
- Review findings: Resolved Finding 1 (prevent ambiguous current-batch IDs from being restored by historical references) and Finding 2 (enforce strict YYYY-MM-DD calendar-date formatting). External review approval remains pending.
- Fixes or accepted risks: None.
- Known limitations: Phase 3 dimensional warehouse (`dim_*`, `fact_transactions`), fact loading, idempotency/replay, and analytics remain in planned status.
- Next action: Submit Phase 2 corrective fixes for external review approval; wait for approval before starting Phase 3.

### Phase 3 — Warehouse Model, Loading, Idempotency, and Reconciliation

- Status: VERIFIED LOCALLY
- Date: 2026-10-16
- Branch: phase/3-warehouse-loading
- Commit SHA: 3b5b262
- GitHub URL: <https://github.com/GouravSharma26/BankFlow/commit/3b5b262>
- Push status: PENDING_PUSH
- Objective: Load valid staging records to a dimensional PostgreSQL warehouse safely, enforce database-level idempotency, implement strict transactional loading, record replay skips as informational issues, and verify count and grouped-currency value reconciliation.
- Changes delivered:
  - `sql/03_warehouse_schema.sql` and `src/bankflow/warehouse/schema.py`:
    Created warehouse schema and conformed dimensions (`dim_date` pre-populated 2020–2035 via `generate_series`, `dim_transaction_type` seeded with 6 types, `dim_branch`, `dim_customer`, `dim_account`) and `fact_transactions` with `CONSTRAINT uq_fact_transactions_source_event UNIQUE (source_system, transaction_id)`.
  - `src/bankflow/warehouse/models.py`:
    Implemented `WarehouseLoadingSummary` and `ReconciliationReport` data models.
  - `src/bankflow/warehouse/loader.py`:
    Implemented `WarehouseLoader` with row-level batch lifecycle guards (`FOR UPDATE`, requiring `SUCCEEDED` or `SUCCEEDED_WITH_REJECTIONS` and `validated_at IS NOT NULL`), relational ordering (branches -> customers -> accounts -> facts), atomic transaction scope, database idempotency (`ON CONFLICT (source_system, transaction_id) DO NOTHING RETURNING transaction_key`), replay skip accounting (`records_skipped`), and logging informational `RULE_SOURCE_REPLAY_SKIPPED` issues with `DISPOSITION_SKIPPED`.
  - `src/bankflow/warehouse/reconciliation.py`:
    Implemented `ReconciliationEngine` verifying count invariants (`staged == valid + rejected`, `quarantined == rejected`, `valid_stg_txns == inserted + skipped`) and grouped monetary values by `(currency, status)`. Persists `reconciliation_status` (`RECONCILED` or `UNRECONCILED`) on `monitoring.etl_batch_runs`.
  - `src/bankflow/__main__.py`:
    Updated `init-db` to include warehouse schema, added `load`, `reconcile`, and `run` (full pipeline) CLI commands, and enhanced `batch-status`.
  - `tests/test_warehouse.py` & `tests/test_warehouse_integration.py`:
    Added 3 unit tests and 8 live PostgreSQL integration tests covering schema creation, clean batch loading, idempotency/replay, lifecycle guards, transactional rollback on error, reconciliation discrepancy detection, defective batch quarantine boundaries, and CLI commands. Total test suite increased from 46 to 57 passing tests (0 skipped, 0 failed).
  - Documentation:
    Updated `docs/data_dictionary.md` (Section 5: documented all 6 warehouse tables), `docs/design_decisions.md` (TD-012, TD-013, TD-018 accepted), `DEVELOPMENT_CHECKLIST.md` (marked all Phase 3 tasks complete).
- Tests/commands executed:
  - `pytest -v tests/test_warehouse.py` (3 passed in 0.19s)
  - `pytest -v tests/test_warehouse_integration.py` (8 passed in 80s against live PostgreSQL test container)
  - `pytest -v` (57 passed in 167s across all unit and integration suites)
  - `git diff --check` (clean, 0 errors)
- Test outcomes: 57 passed, 0 skipped, 0 failed.
- Acceptance evidence:
  - All 57 tests passing against live PostgreSQL `bankflow_test`.
  - Clean batches populate `dim_branch`, `dim_customer`, `dim_account`, and `fact_transactions` with surrogate keys and valid foreign key references.
  - Replay of an identical batch or existing events inserts 0 new facts, records N skipped replays, produces zero duplicates in `fact_transactions`, logs `RULE_SOURCE_REPLAY_SKIPPED` INFO issues, and reconciles cleanly.
  - Simulated failure during fact loading completely rolls back the database transaction, leaving zero partial records in the warehouse.
  - Mutating valid counts or amounts immediately flags `reconciliation_status = 'UNRECONCILED'` with explicit mismatch diagnostics.
  - CLI commands `load`, `reconcile`, `batch-status`, and `run` operate seamlessly.
- Known limitations: Phase 4 SQL analytics reports and Phase 5 dashboard are next phases.
- Next action: Commit Phase 3 changes, push branch `phase/3-warehouse-loading` to GitHub, and provide Phase 3 handoff report for review.

## Phase Entry Template

```markdown
### Phase N — <phase name>

- Status: VERIFIED / BLOCKED / PARTIALLY COMPLETE
- Date:
- Branch:
- Commit SHA:
- GitHub URL:
- Push status:
- Objective:
- Changes delivered:
- Tests/commands executed:
- Test outcomes (pass/fail/skip):
- Acceptance evidence:
- Review findings:
- Fixes or accepted risks:
- Known limitations:
- Next action:
```
