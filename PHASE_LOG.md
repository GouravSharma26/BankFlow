# BankFlow — Phase Log and Review Record

> Append-only project history. Record verified outcomes, not intentions. Do not mark work completed until the acceptance evidence is available.

## Current Status

- Overall status: `RELEASE MERGED & VERIFIED — BankFlow CLI & Dimensional Warehouse Release`
- Current phase: `Release Complete — Hotfix Merged (PR #4 at e30750d)`
- Last approved implementation phase: `Phase 3 — Warehouse Model, Loading, Idempotency, and Reconciliation (Merged into main)`
- GitHub repository: <https://github.com/GouravSharma26/BankFlow>
- Baseline commit: `cc2b371`
- Latest main commit: `e30750d`
- Release PR: PR #3 (`4991e30`) & Hotfix PR: PR #4 (`e30750d`)
- Branch: `main`

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

- Status: VERIFIED AND APPROVED
- Date: 2026-10-16
- Branch: phase/2-validation-quarantine
- Commit SHA: 5e94dfc (Implementation) / d51e4e3 (Documentation) / d4e3c02 (Review approval)
- GitHub URL: <https://github.com/GouravSharma26/BankFlow/tree/phase/2-validation-quarantine>
- Push status: Pushed to origin/phase/2-validation-quarantine and approved at commit d4e3c02
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
- Review findings: Resolved Finding 1 (prevent ambiguous current-batch IDs from being restored by historical references) and Finding 2 (enforce strict YYYY-MM-DD calendar-date formatting). External review approved at commit `d4e3c02`.
- Fixes or accepted risks: None.
- Known limitations: Phase 3 dimensional warehouse (`dim_*`, `fact_transactions`), fact loading, idempotency/replay, and analytics remain in planned status.
- Next action: Submit Phase 2 corrective fixes for external review approval; wait for approval before starting Phase 3.

### Phase 3 — Warehouse Model, Loading, Idempotency, and Reconciliation

- Status: IMPLEMENTED (Merged to main at 7fc540d, review requested corrections)
- Date: 2026-10-16
- Branch: phase/3-warehouse-loading
- Commit SHA: 3b5b262 (Implementation) / 10cd29b (Documentation) / 7fc540d (Merged baseline on main)
- GitHub URL: <https://github.com/GouravSharma26/BankFlow/commit/7fc540d46638ad08d80c543b6566185619865040>
- Push status: Pushed to origin/phase/3-warehouse-loading and merged to main at 7fc540d
- Objective: Load valid staging records to a dimensional PostgreSQL warehouse safely, enforce database-level idempotency, implement strict transactional loading, record replay skips as informational issues, and verify count and grouped-currency value reconciliation.
- Review findings: 8 review findings received requiring corrections (whitespace normalization in joins, conflicting replay payload detection/quarantine, non-zero CLI exit code on unreconciled runs, 2-decimal monetary scale validation, historical-dimension dependency preflight guards, batch lifecycle allowlist, date dimension range extension, and phase status documentation).
- Next action: Implement review corrections in a follow-up commit on `phase/3-warehouse-loading`.

### Phase 3 — Review Findings and Data-Integrity Corrections

- Status: VERIFIED LOCALLY — AWAITING REVIEW
- Date: 2026-10-17
- Branch: phase/3-warehouse-loading
- Commit SHA: 40ed5ff
- GitHub URL: <https://github.com/GouravSharma26/BankFlow/commit/40ed5ff>
- Push status: In progress (push to origin/phase/3-warehouse-loading)
- Objective: Address all 8 Phase 3 review findings covering warehouse join normalization, conflicting-replay detection and quarantine, CLI non-zero exit codes on reconciliation failure, 2-decimal monetary scale enforcement, historical-dimension dependency preflight guards, batch lifecycle status allowlist, extended date dimension coverage, and documentation consistency.
- Changes delivered:
  1. Whitespace-normalized warehouse joins (Finding 1): Updated `src/bankflow/warehouse/loader.py` to use `TRIM()` in warehouse dimension and fact join queries (`TRIM(st.account_id) = da.account_id`, `TRIM(st.transaction_type) = dtt.transaction_type_code`, etc.) and lookup queries, ensuring valid whitespace-padded staging records correctly resolve and populate dimensions/facts without altering original raw staging values. Added live integration test `test_warehouse_whitespace_normalized_joins_and_loading`.
  2. Conflicting replay payload detection and quarantine (Finding 2): Updated `src/bankflow/warehouse/loader.py` and `src/bankflow/warehouse/reconciliation.py`. When a candidate fact encounters an existing `(source_system, transaction_id)` in the warehouse:
     - If the payload matches (`amount`, `currency`, `status`, `account_id`, `transaction_timestamp`), it is recorded as an informational replay skip (`records_skipped += 1`, `RULE_SOURCE_REPLAY_SKIPPED`, `DISPOSITION_SKIPPED`).
     - If the payload conflicts (e.g. differing amount, currency, status, or account), it is NOT counted as a replay skip. Instead, it is logged as an error (`RULE_CONFLICTING_REPLAY_PAYLOAD`, `SEVERITY_ERROR`, `DISPOSITION_REJECTED`), quarantined in `quarantine.quarantined_records`, transferred from `records_valid` to `records_rejected`, the batch transitions to `SUCCEEDED_WITH_REJECTIONS`, and reconciliation flags an explicit discrepancy (`UNRECONCILED`). Added live integration test `test_warehouse_conflicting_replay_payload_rejected_and_quarantined`.
  3. Non-zero CLI exit code on reconciliation failure (Finding 3): Updated `src/bankflow/__main__.py` in `load`, `reconcile`, and `run` commands to call `sys.exit(1)` whenever reconciliation fails (`reconciliation_status != 'RECONCILED'` or `not report.is_reconciled`), while preserving formatted diagnostic output. Added integration tests in `test_cli_unreconciled_returns_nonzero_exit_code` verifying non-zero exit codes for `reconcile`, `load`, and `run`.
  4. Monetary scale validation (Finding 4): Updated `src/bankflow/validation/validator.py` to enforce maximum 2 decimal places (`parsed_decimal.as_tuple().exponent < -2`) during row validation, rejecting numbers such as `10.001` under `RULE_AMOUNT_RULE_VIOLATION` before warehouse insertion. Added unit test `test_amount_decimal_scale_validation` and integration test `test_amount_with_more_than_two_decimals_rejected_in_integration`.
  5. Historical dimension dependency preflight guard (Finding 5): Implemented `_preflight_dimension_checks()` in `WarehouseLoader` to verify that all customers, branches, and accounts referenced by a batch's valid records exist in the warehouse dimensions before attempting to insert facts. If upstream dependencies are unpopulated, load raises `ValueError` with explicit missing identifiers. Added integration test `test_warehouse_historical_dimension_dependency_preflight_guard`.
  6. Explicit batch lifecycle status allowlist (Finding 6): Hardened `WarehouseLoader.load_batch()` with strict allowlist check `if status not in (BATCH_STATUS_SUCCEEDED, BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS): raise ValueError(...)` ensuring unsupported states cannot proceed even if `validated_at` is non-null. Added test coverage in `test_warehouse_lifecycle_guard_rejects_ineligible_batches`.
  7. Extended date dimension range (Finding 7): Expanded default `dim_date` pre-population in `sql/03_warehouse_schema.sql` and `src/bankflow/warehouse/schema.py` to 2015–2040, and implemented dynamic dimension expansion `_ensure_batch_dates_covered()` in `WarehouseLoader` to insert any missing date rows automatically. Added integration test `test_warehouse_extended_date_dimension_support`.
  8. Documentation consistency (Finding 8): Updated `DEVELOPMENT_CHECKLIST.md` and `PHASE_LOG.md` recording Phase 2 approval (commit `d4e3c02`), main branch merge baseline (`7fc540d`), and Phase 3 review status.
- Tests/commands executed:
  - `pytest -v tests/test_validation.py` (8 passed)
  - `pytest -v tests/test_warehouse_integration.py` (15 passed)
  - `pytest -v` (65 passed, 0 skipped, 0 failed in 253s against live PostgreSQL `bankflow_test` instance)
  - `git diff --check` (clean, 0 warnings/errors)
- Test outcomes: 65 passed, 0 skipped, 0 failed.
- Acceptance evidence:
  - 65 automated tests passing across the entire suite.
  - Conflicting transaction replays trigger quarantine and fail reconciliation with exit code 1.
  - Whitespace-padded staging records resolve correctly into dimensions and facts.
  - 10.001 is quarantined with `AMOUNT_RULE_VIOLATION`.
  - Unloaded upstream dependencies halt loading during preflight.
  - Unsupported lifecycle states are rejected.
  - Transactions dated 2014 and 2042 dynamically generate date keys and load successfully.
- Review findings: All 8 review findings resolved.
- Next action: Submit Phase 3 review corrections for review.

### Phase 3 — Final Replay-Integrity and Concurrency Corrections

- Status: VERIFIED LOCALLY — AWAITING REVIEW
- Date: 2026-10-17
- Branch: phase/3-warehouse-loading
- Commit SHA: 558b002
- GitHub URL: <https://github.com/GouravSharma26/BankFlow/commit/558b002>
- Push status: In progress (push to origin/phase/3-warehouse-loading)
- Objective: Address final Phase 3 review findings on complete fact payload replay comparison (Finding 1) and race-safe concurrent warehouse loading (Finding 2) without starting Phase 4 or rebuilding completed components.
- Changes delivered:
  1. Complete fact payload replay comparison (Finding 1):
     - Updated `WarehouseLoader._load_facts()` in `src/bankflow/warehouse/loader.py` to compare all 7 immutable fields of the fact record: `amount`, `currency`, `status`, `account_id`, `transaction_timestamp`, `transaction_type`, and `channel` (resolving existing account and transaction type via conformed dimensions).
     - Events are classified as identical replays (`RULE_SOURCE_REPLAY_SKIPPED`, `DISPOSITION_SKIPPED`) ONLY when all 7 fields match.
     - Reused event identities with any differing immutable field (including changed `transaction_type` or changed `channel` independently) are classified as `RULE_CONFLICTING_REPLAY_PAYLOAD`, recorded in `monitoring.data_quality_issues` (`SEVERITY_ERROR`, `DISPOSITION_REJECTED`), quarantined in `quarantine.quarantined_records`, deducted from batch `records_valid`, added to `records_rejected`, transition the batch to `SUCCEEDED_WITH_REJECTIONS`, and trigger reconciliation discrepancy.
     - Updated `ReconciliationEngine._reconcile_monetary_values()` in `src/bankflow/warehouse/reconciliation.py` to join `dim_transaction_type` and compare `transaction_type_code` and `channel` alongside account, timestamp, amount, currency, and status.
     - Added live integration test `test_warehouse_conflicting_replay_changed_type_and_channel_independently` in `tests/test_warehouse_integration.py` asserting independent type and channel changes are quarantined and fail reconciliation.
  2. Concurrency-safe atomic replay handling (Finding 2):
     - Eliminated race-prone select-then-insert pattern in `WarehouseLoader._load_facts()`. Implemented atomic PostgreSQL uniqueness conflict path using:
       `INSERT INTO warehouse.fact_transactions (...) ON CONFLICT (source_system, transaction_id) DO NOTHING RETURNING transaction_key;`
     - When insertion does not return a key (conflict detected), atomically retrieves the existing committed event with dimension joins and performs complete 7-field immutable payload comparison.
     - Atomically logs identical replays or conflicting replays and executes the batch accounting adjustment in `monitoring.etl_batch_runs` once inside the transaction.
     - Hardened `init_warehouse_schema()` in `src/bankflow/warehouse/schema.py` and `sql/03_warehouse_schema.sql` against concurrent schema initialization deadlocks by verifying schema existence before attempting DDL/DML, adding `WHERE NOT EXISTS` guards on dimension seeding, and wrapping execution in `transaction(conn)`.
     - Added live multi-threaded PostgreSQL integration test `test_warehouse_concurrent_loads_atomic_replay_safety` using separate database connections and threading barriers to load identical and conflicting event replays concurrently across separate batches. Verified 0 unhandled uniqueness exceptions, exactly 1 fact record created, and appropriate skip/quarantine classification on the losing thread.
- Tests/commands executed:
  - `pytest -v tests/test_warehouse_integration.py -k "test_warehouse_conflicting_replay_changed_type_and_channel_independently"` (1 passed)
  - `pytest -v tests/test_warehouse_integration.py -k "test_warehouse_concurrent_loads_atomic_replay_safety"` (1 passed)
  - `pytest -v tests/test_warehouse_integration.py` (17 passed, 0 skipped, 0 failed in 179s against PostgreSQL)
  - `pytest -v` (67 passed, 0 skipped, 0 failed across full repository suite in 267s against PostgreSQL `bankflow_test`)
  - `git diff --check` (clean, 0 warnings/errors)
- Test outcomes: 67 passed, 0 skipped, 0 failed.
- Acceptance evidence:
  - Live PostgreSQL multi-connection concurrent loads execute without deadlocks or uniqueness violations.
  - Independent changes to `transaction_type` or `channel` for existing event identities are rejected as `RULE_CONFLICTING_REPLAY_PAYLOAD` and quarantined.
  - Zero duplicate fact records inserted under concurrent identical or conflicting loads.
  - Reconciliation fails with discrepancy when conflicting payloads are detected.
- Review findings: Finding 1 and Finding 2 resolved.
- Known limitations: Phase 3 review remains pending external review; Phase 4 not started.
- Next action: Package CLI release, update documentation, and prepare PR for main.

### BankFlow CLI Release — Fast Resume Release Package

- Status: VERIFIED LOCALLY — READY FOR PR MERGE
- Date: 2026-10-17
- Branch: phase/3-warehouse-loading
- Scope: Applied release patch for a truthful, reproducible, resume-ready Python/PostgreSQL CLI ETL and warehouse release.
- Changes delivered:
  1. Updated `README.md` to accurately describe the delivered Python/PostgreSQL CLI ETL pipeline, validation/quarantine engine, dimensional star schema, replay safety, reconciliation, and analytics queries. Explicitly scoped project as a CLI-based warehouse; marked BI dashboards and cloud scheduling as deferred.
  2. Added `sql/04_analytics_queries.sql` containing 6 repeatable reporting queries:
     - Monthly transaction volume and gross amount by currency (grouping by currency).
     - Transaction mix by type, family, channel, and currency.
     - Branch and regional activity.
     - Data-quality issue summary by rule, severity, and disposition.
     - Recent batch health and source-to-warehouse reconciliation status.
     - Quarantine volume by entity and primary rule code.
     Verified execution on PostgreSQL container.
  3. Added `.github/workflows/ci.yml` providing GitHub Actions CI workflow running on push to `main` and `phase/3-warehouse-loading`, and PRs targeting `main`. Provisions PostgreSQL 17, initializes `bankflow_test`, installs `.[dev]`, enforces `BANKFLOW_REQUIRE_INTEGRATION_TESTS="1"`, and runs the full test suite.
  4. Added `RELEASE_CHECKLIST.md` tracking verified release criteria and deferred features.
  5. Updated `HUMAN_SETUP.md` with complete CLI reference commands and deferred scope.
  6. Verified end-to-end execution of clean synthetic dataset (`release-clean-001`: 170 staged, 170 valid, 0 rejected, 100 facts inserted, 0 replays, RECONCILED).
  7. Verified defect-injected dataset (`release-defects-001`: 170 staged, 156 valid, 14 rejected, 86 replays skipped, 1 conflicting replay quarantined, UNRECONCILED with non-zero exit code).
  8. Full test suite: 67 passed, 0 skipped, 0 failed in 267s against PostgreSQL test database with `BANKFLOW_REQUIRE_INTEGRATION_TESTS="1"`.
- Tests/commands executed:
  - `python -m pip install -e ".[dev]"`
  - `python -m pytest tests -v` with `BANKFLOW_REQUIRE_INTEGRATION_TESTS="1"` (67 passed, 0 skipped, 0 failed)
  - `python -m bankflow generate --output-dir data/samples --seed 42 --branches 5 --customers 25 --accounts 40 --transactions 100`
  - `python -m bankflow run --input-dir data/samples --batch-id release-clean-001`
  - `python -m bankflow batch-status release-clean-001`
  - `python -m bankflow generate --output-dir data/defective-sample --seed 42 --transactions 100 --with-defects`
  - `python -m bankflow run --input-dir data/defective-sample --batch-id release-defects-001`
  - `python -m bankflow batch-status release-defects-001`
  - Executed `sql/04_analytics_queries.sql` on live database
  - `git diff --check` (clean, 0 warnings/errors)
- Test outcomes: 67 passed, 0 skipped, 0 failed.
- Acceptance evidence:
  - End-to-end clean run succeeded and verified.
  - Defect-injected run quarantined records, reported discrepancies, and failed reconciliation.
  - All 6 SQL analytics queries executed and returned valid results.
  - Full automated suite passes with mandatory integration tests.
- Known limitations: BI dashboard (Power BI/Metabase) and cloud scheduling/managed deployment are deferred for future roadmap phases.
- Next action: Completed. Release PR #3 merged into main at 4991e30; followed by P0 hotfix PR #4 merged at e30750d.

### Antigravity Hotfix — CI Test Failure Reporting & Date Dimension Alignment

- Status: VERIFIED & MERGED
- Date: 2026-10-17
- Branch: hotfix/ci-test-failure-reporting (merged into main)
- Commit SHA: 8dd69a5 (hotfix branch) / e30750d (main merge commit)
- Pull Request: PR #4 (<https://github.com/GouravSharma26/BankFlow/pull/4>)
- GitHub CI Run (PR #4): <https://github.com/GouravSharma26/BankFlow/actions/runs/39003312333> (SUCCESS, 67 passed in 4.25s)
- GitHub CI Run (main): <https://github.com/GouravSharma26/BankFlow/actions/runs/39003397068> (SUCCESS, 67 passed in 3.71s)
- Push status: Pushed to `origin/hotfix/ci-test-failure-reporting`, merged into `origin/main` via PR #4
- Objective: Fix date dimension SQL parameter count mismatch in `_ensure_batch_dates_covered` and ensure CI immediately fails on real pytest failures with robust pipefail and always-uploaded test artifacts.
- Changes delivered:
  1. `src/bankflow/warehouse/loader.py`: Corrected `_ensure_batch_dates_covered` parameter tuple to `(min_date, max_date)` matching the 2 `%s` placeholders in `FROM generate_series(%s::DATE, %s::DATE, '1 day'::INTERVAL) d`. Resolves `TypeError: not all arguments converted during string formatting` in `test_warehouse_extended_date_dimension_support`.
  2. `.github/workflows/ci.yml`:
     - Removed `continue-on-error: true` from the pytest test step.
     - Removed misleading JUnit root-attribute evaluator that masked test failures.
     - Enforced `set -euo pipefail` on `python -m pytest tests -v --tb=short --junitxml=pytest-junit.xml 2>&1 | tee pytest.log` so any failure immediately fails the step.
     - Preserved `if: always()` on `Upload test artifacts` ensuring `pytest.log` and `pytest-junit.xml` are always uploaded on failure or success.
     - Added `"hotfix/**"` to push branch triggers.
  3. `.gitignore`: Added `pytest.log`, `pytest-junit.xml`, and `.playwright-mcp/` to ignored files.
  4. `RELEASE_CHECKLIST.md`: Updated checklist to reflect merged PR state and verified hotfix handoff.
- Tests/commands executed:
  - `python -m pytest tests/test_warehouse_integration.py::test_warehouse_extended_date_dimension_support -v` (PASSED against PostgreSQL test db after resetting date range)
  - Full automated suite: `powershell -Command "$env:BANKFLOW_REQUIRE_INTEGRATION_TESTS='1'; python -m pytest tests -v --tb=short --junitxml=pytest-junit.xml"` (67 passed, 0 skipped, 0 failed in 267.87s)
  - `git diff --check` (clean, 0 warnings/errors)
  - GitHub Actions CI (PR #4): 67 passed, 0 skipped, 0 failed in 4.25s
  - GitHub Actions CI (main): 67 passed, 0 skipped, 0 failed in 3.71s
- Acceptance evidence:
  - PR #4 CI run <https://github.com/GouravSharma26/BankFlow/actions/runs/39003312333> verified green with all 67 tests passing.
  - Main merge CI run <https://github.com/GouravSharma26/BankFlow/actions/runs/39003397068> verified green with all 67 tests passing.
- Known limitations: BI dashboard (Power BI/Metabase) and cloud scheduling/managed deployment are deferred for post-resume roadmap phases.
- Next action: Repository release is complete and verified on `main`. Proceed to subsequent roadmap phases only upon explicit user request.

### Phase 4 — SQL Analytics and Metric Definitions

- Status: VERIFIED
- Date: 2026-10-17
- Branch: phase/4-sql-analytics-metrics
- Commit SHA: pending initial commit
- GitHub URL: pending PR creation
- Push status: In progress (pushing branch and opening review PR to main)
- Objective: Implement comprehensive SQL analytics, conformed analytical reporting views, precise metric definitions contract, CLI reporting commands, and PostgreSQL integration tests for BankFlow Phase 4.
- Changes delivered:
  1. `sql/05_reporting_views.sql`: Created conformed views in dedicated `reporting` schema:
     - `v_daily_transaction_summary`: Daily volume, gross event value, and completed/failed counts by UTC date and currency.
     - `v_deposit_withdrawal_analysis`: Completed cash-flow activity comparing deposits vs withdrawals with explicit completed-status filtering.
     - `v_branch_channel_activity`: Channel and branch distribution of transaction events and completed volume.
     - `v_transaction_type_mix`: Portfolio breakdown across standard transaction types, event share, and value share.
     - `v_data_quality_summary`: Multi-issue accounting distinguishing distinct quality defects, affected source rows, and impacted batches.
     - `v_pipeline_execution_health`: Batch execution status, lifecycle duration (seconds), validation efficiency, and reconciliation outcomes.
     - `v_quarantine_inventory`: Quarantined record inventory grouped by entity, primary rule code, and batch.
  2. `sql/04_analytics_queries.sql`: Updated with 7 executable reporting queries matching the canonical reporting areas.
  3. `src/bankflow/analytics/`: Added `schema.py` with idempotent `init_reporting_schema(conn)`.
  4. `src/bankflow/__main__.py`: Updated `init-db` to initialize reporting schema; added `bankflow report <report_name>` CLI command with formatting and filters (`--currency`, `--status`, `--entity`, `--batch-id`, `--limit`).
  5. `tests/test_analytics_integration.py`: Added 11 PostgreSQL integration tests verifying all 7 reporting views against deterministic known-answer fixtures, empty-state behavior, `sql/04_analytics_queries.sql` execution, CLI report command formatting, and `EXPLAIN` query plan index scans.
  6. `tests/test_warehouse_integration.py`: Updated `postgres_test_db` fixture to initialize the reporting schema.
  7. `docs/metric_definitions.md`: Fully updated from planned draft to verified contract with comprehensive formulas, grains, dimensions, status handling, reversal semantics, and empty/zero-division behavior.
  8. `docs/data_dictionary.md`: Added Section 6 covering all 7 reporting views with column definitions, types, nullability, derivations, and meanings.
  9. `docs/architecture.md`: Updated Section 3.7 with reporting layer architecture, conformed analytical views, and metric rules.
  10. `docs/design_decisions.md`: Accepted TD-014 (Grouped currencies only) and added TD-019 (Dedicated `reporting` schema with conformed analytical views).
  11. `DEVELOPMENT_CHECKLIST.md`: Reconciled Phase 3 truthfully as merged to main with CI passing, and checked off Phase 4 items with verified exit criteria.
  12. `README.md`: Documented `bankflow report` CLI command, conformed reporting views, and reporting rules.
- Tests/commands executed:
  - `python -m pytest tests/test_analytics_integration.py -v` (11 passed in 123.98s)
  - Full suite: `powershell -Command "$env:BANKFLOW_REQUIRE_INTEGRATION_TESTS='1'; python -m pytest tests -v"` (78 passed, 0 skipped, 0 failed in 390.65s)
  - `git diff --check` (clean, 0 warnings/errors)
- Test outcomes: 78 passed, 0 skipped, 0 failed.
- Acceptance evidence:
  - All 7 reporting views executed successfully against deterministic known-answer datasets loaded in PostgreSQL.
  - Known-answer assertions verified: daily counts, gross amounts, completed deposit/withdrawal ratios, branch/channel volumes, type mix, multi-issue vs affected-row accounting, batch duration and reconciliation statuses, and quarantine summaries.
  - Query plans verified via `EXPLAIN` demonstrating index usage (`dim_date_pkey`, `dim_transaction_type_pkey`, `dim_branch_pkey`).
  - Zero-division and empty dataset tests confirmed queries produce empty or 0 results without exceptions.
- Review findings: None in tested scope.
- Fixes or accepted risks: Staging raw currency column constraint is `VARCHAR(10)`, test fixtures use ISO-like codes (`XXX`). `quarantined_records` timestamp is `quarantined_at`.
- Known limitations: Hosted Lovable prototype is a synthetic frontend mockup not connected to PostgreSQL. BI dashboard (Power BI/Metabase) is planned for Phase 5.
- Next action: Submit Phase 4 PR for user review; do not start Phase 5.

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
