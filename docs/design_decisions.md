# BankFlow — Technical Decisions and Decision Log

> This file records the current choices and the reason for them. A decision is not final until it is implemented, tested, and confirmed in the repository. Keep this log short enough to review, but specific enough that an engineer can understand trade-offs.

## 1. Current Planned Decisions

| ID | Topic | Current choice | Status | Reason / guardrail |
|---|---|---|---|---|
| TD-001 | Primary language | Python 3.12+ | Accepted | Standard ecosystem for ETL and testability; running Python 3.12.6. |
| TD-002 | Warehouse database | PostgreSQL | Accepted | Relational constraints, transactions, views, and query analysis are central to the learning goal. |
| TD-003 | Input format | CSV | Accepted | Easy to inspect, generate, version as small fixtures, and explain in a demo. |
| TD-004 | Monetary representation | Python `Decimal` + PostgreSQL `NUMERIC` | Accepted | Avoid binary floating-point rounding in monetary calculations. |
| TD-005 | Testing | pytest | Accepted | Allows unit, database integration, and end-to-end verification. |
| TD-006 | CI | GitHub Actions | Planned | Makes tests visible and repeatable on code changes. |
| TD-007 | Dashboard | Lovable Analytics Console (Web App) | Accepted | Selected purpose-built Lovable web console rather than creating a second Power BI/Metabase dashboard; recorded in TD-020. |
| TD-008 | Python DB access | psycopg2-binary | Accepted | Direct, high-performance SQL execution and batch staging with zero ORM overhead. |
| TD-009 | Orchestration | Manual CLI first (Click) | Accepted | Prove correctness before introducing scheduler complexity. |
| TD-010 | Containerization | Docker Compose for local PostgreSQL | Accepted | Provides one-command local PostgreSQL 17 setup with primary and test databases. |
| TD-011 | Data content | Synthetic records only | Accepted | Prevent privacy and security risks; no live systems or customer records. |
| TD-012 | Warehouse model | Dimensional star schema | Accepted | Clear analytical model with fact/dimension relationships. |
| TD-013 | Event replay | Database-enforced idempotency | Accepted | Prevent duplicate facts even across repeated/concurrent attempts. |
| TD-014 | Currency reporting | Grouped currencies only | Accepted | Never sum incomparable currencies without an explicit conversion model; all views group by currency. |
| TD-015 | Batch status | Explicit lifecycle states persisted in monitoring | Accepted | Make process state and failure/recovery outcomes inspectable. |
| TD-019 | Reporting schema | Dedicated `reporting` schema with conformed views | Accepted | Centralize metric definitions in PostgreSQL views for SQL reports, CLI, and BI tools. |

## 2. Decision-Making Rules

For each new technology or non-trivial alternative, document:

1. Problem or requirement that prompts the decision.
2. Options considered, including the simplest option.
3. Chosen option and why it fits this project's size and timeline.
4. Impact on testability, setup, data correctness, and ongoing maintenance.
5. Whether this is required for MVP or deferred.
6. The date/phase and evidence that validated the choice.

Do not add a tool because it appears on job descriptions alone. A tool should solve a specific problem and be demonstrable in the code.

## 3. Explicit MVP Guardrails

- No Kafka, Spark, Airflow, or distributed architecture before the core batch ETL is correct.
- No cloud deployment required for MVP.
- No external AI/LLM service is needed for this project.
- No real bank/customer data or live banking API.
- No unmeasured claims such as “optimized by 40%”.
- No currency conversion until a real, clearly synthetic FX-rate model and reporting rule are defined.
- No account balance calculations by naively summing every event amount.

## 4. Decision Log Template

Append entries below rather than silently changing an existing decision.

```markdown
### TD-<number> — <title>
- Date / phase:
- Status: Proposed / Accepted / Superseded
- Context:
- Options considered:
- Decision:
- Rationale:
- Consequences / trade-offs:
- Verification or evidence:
- Supersedes (if applicable):
```

## 5. Actual Implementation Updates

### TD-008 — PostgreSQL Access via psycopg2-binary
- Date / phase: 2026-10-16 / Phase 1
- Status: Accepted
- Context: BankFlow needs a robust, parameterized database access layer for PostgreSQL schema initialization, high-volume batch staging, and transactional execution.
- Options considered:
  1. SQLAlchemy Core / ORM: flexible multi-dialect abstraction, but introduces additional layers, migration overhead, and extra dependencies.
  2. psycopg2-binary: established Python-PostgreSQL driver, native support for batch operations (`execute_batch`), transactions, and parameterized SQL without ORM magic.
  3. psycopg (v3): modern rewrite, but psycopg2-binary is already pre-installed in the local environment and provides battle-tested stability.
- Decision: Select `psycopg2-binary>=2.9.0` as the primary database driver.
- Rationale: Staging and data warehousing rely on explicit relational SQL, schemas, and transactions. An ORM is not needed and adds complexity for batch ETL.
- Consequences / trade-offs: SQL statements are written explicitly in `.sql` files and Python constants, which maximizes transparency and learning value for SQL analytics.
- Verification or evidence: Database connection module (`bankflow.db`), schema initializer (`bankflow.staging.schema`), and staging loader (`bankflow.staging.loader`) successfully verified in tests.

### TD-010 — Local PostgreSQL via Docker Compose
- Date / phase: 2026-10-16 / Phase 1
- Status: Accepted
- Context: Local PostgreSQL installation may have variable authentication configs, existing services, or credential mismatches that make onboarding and integration testing difficult across different developer machines.
- Options considered:
  1. Rely solely on host-installed PostgreSQL service.
  2. Provide a declarative `docker-compose.yml` for PostgreSQL 17 with an automated test database initialization script.
- Decision: Provide `docker-compose.yml` with `postgres:17-alpine`, persistent volume `bankflow_postgres_data`, and initialization script `docker/01-init-test-db.sql`.
- Rationale: Gives an instant, repeatable, reproducible local database environment for both the primary warehouse (`bankflow`) and the test database (`bankflow_test`), with configurable port mapping to avoid host collisions.
- Consequences / trade-offs: Requires Docker Desktop or Docker engine, but developers without Docker can still point to any existing PostgreSQL instance via `.env`.
- Verification or evidence: `docker compose config` validates cleanly. Container startup and healthchecks verified.

### TD-016 — Multi-Issue Recording with Row-Level Accounting Invariant
- Date / phase: 2026-10-16 / Phase 2
- Status: Accepted
- Context: A staged row can have multiple distinct defects (e.g., missing transaction ID, invalid amount, and unsupported status). The validator needs to decide whether to stop at the first fatal error or record all detectable defects, and how to account for the row in batch statistics.
- Options considered:
  1. Fail-fast per row: stop evaluating a row upon encountering the first error. Simpler, but conceals downstream defects, forcing multiple repair/re-ingest cycles.
  2. Multi-issue recording per row with strict row accounting: record all detected issues in `monitoring.data_quality_issues`, but count the row as exactly one rejected row in `records_rejected`.
- Decision: Adopt multi-issue recording per row with strict row accounting (`records_evaluated = records_valid + records_rejected`).
- Rationale: Upstream data engineers and reviewers get a complete, immediate diagnostic picture of all issues on a rejected row, while reconciling batch counts remains mathematically consistent without double-counting.
- Consequences / trade-offs: `total_issues_count` can exceed `records_rejected`. Documented as distinct metrics in `monitoring.data_quality_issues` vs `monitoring.etl_batch_runs`.
- Verification or evidence: Verified in `tests/test_validation.py::test_batch_validation_summary_accounting` and `tests/test_validation_integration.py::test_defective_dataset_validation_and_quarantine`.

### TD-017 — Traceable Quarantine via Foreign Key Reference Without Staging Duplication
- Date / phase: 2026-10-16 / Phase 2
- Status: Accepted
- Context: Quarantined records must remain traceable to the original staged source row (preserving raw payloads, whitespace, and surplus fields) without bloating the database by duplicating large text/payloads.
- Options considered:
  1. Duplicate copy: copy the complete raw payload and columns into a dedicated `quarantine.quarantined_transactions` table. Causes double storage and risks drift.
  2. Foreign-key reference + diagnostic view: store quarantine metadata (`quarantine_id`, `batch_id`, `source_row_id`, `primary_rule_code`, `issue_count`) in `quarantine.quarantined_records`, referencing `source_row_id` in staging. Provide a relational view `quarantine.vw_quarantined_transactions` joining to `staging.stg_transactions`.
- Decision: Adopt foreign-key reference with a diagnostic relational view (`quarantine.vw_quarantined_transactions`).
- Rationale: Zero raw data duplication, full relational integrity (`ON DELETE CASCADE` on batch), instant access to original raw values, and full traceability.
- Consequences / trade-offs: Quarantined rows depend on `staging.stg_transactions` remaining intact during the lifecycle of the batch.
- Verification or evidence: Verified in `tests/test_validation_integration.py::test_defective_dataset_validation_and_quarantine`.

### TD-012 — Dimensional Star Schema with Static Date and Seeded Transaction Types
- Date / phase: 2026-10-16 / Phase 3
- Status: Accepted
- Context: Analytical reporting requires a clean dimensional star schema that separates event facts from descriptive entities, while insulating reports from operational OLTP/staging schema mutations.
- Options considered:
  1. Flat denormalized reporting table: simple to load, but duplicates customer and account attributes across every transaction row, making dimension changes difficult to audit.
  2. Normalized 3NF schema: reduces redundancy but requires complex multi-table joins for analytical queries.
  3. Star schema with surrogate keys: `fact_transactions` with foreign keys to conformed dimensions (`dim_date`, `dim_transaction_type`, `dim_branch`, `dim_customer`, `dim_account`).
- Decision: Adopt a dimensional star schema in PostgreSQL `warehouse` schema with integer surrogate primary keys and natural source keys. Pre-populate `dim_date` (2020-2035) via `generate_series` and seed `dim_transaction_type` with accounting classifications.
- Rationale: Optimal balance between query performance, join simplicity, and analytical clarity. Surrogate keys ensure warehouse joins do not depend on external natural key stability.
- Consequences / trade-offs: Dimensions must be loaded/upserted in strict relational order (branches -> customers -> accounts) before fact transactions can resolve foreign keys.
- Verification or evidence: Verified in `tests/test_warehouse_integration.py::test_warehouse_clean_batch_loading_and_reconciliation`.

### TD-013 — Database-Enforced Fact Idempotency via Unique Constraint and Replay Tracking
- Date / phase: 2026-10-16 / Phase 3
- Status: Accepted
- Context: Re-running a batch or replaying files must be completely safe and must never create duplicate facts in `warehouse.fact_transactions`.
- Options considered:
  1. Application-level in-memory deduplication: query existing keys before insert. Vulnerable to race conditions and concurrent workers.
  2. Truncate-and-reload: non-additive, loses incremental load history, destructive to historical data.
  3. Database-enforced uniqueness with `ON CONFLICT DO NOTHING`: add `CONSTRAINT uq_fact_transactions_source_event UNIQUE (source_system, transaction_id)` on `warehouse.fact_transactions`. Use `INSERT ... ON CONFLICT (source_system, transaction_id) DO NOTHING RETURNING transaction_key`.
- Decision: Adopt database-enforced uniqueness constraint with `ON CONFLICT DO NOTHING`.
- Rationale: The database engine guarantees physical idempotency atomically. If an event is replayed, the insert returns nothing, which allows `WarehouseLoader` to accurately increment `records_skipped` and log an informational issue (`RULE_SOURCE_REPLAY_SKIPPED`) with `DISPOSITION_SKIPPED` in `monitoring.data_quality_issues`.
- Consequences / trade-offs: Source systems must guarantee that `(source_system, transaction_id)` uniquely identifies an immutable business transaction event.
- Verification or evidence: Verified in `tests/test_warehouse_integration.py::test_warehouse_idempotency_and_replay_safety`.

### TD-018 — Post-Load Reconciliation with Grouped-Currency Monetary Audit
- Date / phase: 2026-10-16 / Phase 3
- Status: Accepted
- Context: Batch ETL must prove that no records or monetary values were lost, corrupted, or silently discarded between staging, validation, and warehouse layers.
- Options considered:
  1. Row count verification only: fast, but misses monetary truncation or amount mutation defects.
  2. Global sum of amounts across all records: invalid when a batch contains mixed currencies (e.g. summing USD and EUR produces nonsense numbers).
  3. Strict count invariants + monetary value audit grouped by `(currency, status)`: verify `staged == valid + rejected`, `quarantined == rejected`, `valid_staging_txns == inserted + skipped`, and match staging valid transaction sums to warehouse fact sums per `(currency, status)`.
- Decision: Implement `ReconciliationEngine` checking both count invariants and monetary value audits grouped strictly by currency and status.
- Rationale: Adheres to core data engineering principles: never sum disparate currencies without exchange rates; guarantee that every staged dollar/cent is accounted for in either warehouse or quarantine.
- Consequences / trade-offs: Reconciler must exclude historical replays from the current batch's value check so that skipped events do not cause false-positive value discrepancies.
- Verification or evidence: Verified in `tests/test_warehouse_integration.py::test_warehouse_reconciliation_detects_discrepancy` and clean batch reconciliation tests.

### TD-019 — Dedicated Reporting Schema with Conformed Analytical Views
- Date / phase: 2026-10-17 / Phase 4
- Status: Accepted
- Context: Analytical consumers, CLI reporting tools, and potential BI dashboards require a reliable, conformed reporting layer over the warehouse facts and monitoring tables that standardizes metric calculations, eliminates query duplication, and enforces currency isolation.
- Options considered:
  1. Ad-hoc queries in client code: clients write custom SQL directly against `warehouse` and `monitoring`. Highly error-prone; risks diverging metric definitions, inconsistent status filters, and accidentally summing multiple currencies.
  2. Materialized reporting tables refreshed by ETL: high write overhead, potential synchronization lag, and extra storage.
  3. PostgreSQL Views in a dedicated `reporting` schema: conformed views defining canonical metrics directly over `warehouse`, `monitoring`, and `quarantine`.
- Decision: Implement standard PostgreSQL views in a dedicated `reporting` schema (`reporting.v_*`) initialized alongside warehouse tables via `sql/05_reporting_views.sql`.
- Rationale: Views provide zero storage overhead, guaranteed real-time consistency with loaded batches, encapsulation of complex join logic, and a stable contract for downstream dashboards/BI or API consumers.
- Consequences / trade-offs: Query execution time depends on base table indexing. Database indices on `dim_date`, `dim_transaction_type`, `dim_branch`, and `fact_transactions` foreign keys provide index scans without speculative indexing.
- Verification or evidence: Verified via 11 integration tests in `tests/test_analytics_integration.py` executing all 7 views against deterministic known-answer datasets and asserting metric precision.

### TD-020 — Read-Only Reporting API for Lovable Web Console
- Date / phase: 2026-10-17 / Phase 5
- Status: Accepted
- Context: BankFlow required a dashboard frontend for business reporting and pipeline monitoring. An existing purpose-built web console was deployed at `https://bankflow-analytics-console.lovable.app/` using synthetic sample data. The original plan noted Power BI or Metabase (TD-007).
- Options considered:
  1. Build a separate Power BI / Metabase dashboard from scratch: requires proprietary software or heavyweight server instances, redundant given the existing web console.
  2. Implement a secure, read-only REST API (FastAPI) serving the conformed PostgreSQL `reporting` schema to the Lovable console.
- Decision: Select the Lovable web console as the canonical frontend, connected via a dedicated read-only FastAPI service (`src/bankflow/api`).
- Rationale: Avoids duplicating dashboard tools, provides a clean decoupled architecture (browser frontend -> read-only REST API -> PostgreSQL reporting views), enforces least-privilege database roles, eliminates credential exposure, and provides a clear integration contract via `VITE_BANKFLOW_API_BASE_URL`.
- Consequences / trade-offs: Requires a lightweight API runtime (`pip install -e ".[api]"`), packaged as an optional extra so batch CLI users need not install FastAPI or Uvicorn. The public hosted frontend remains in synthetic demo mode until the backend API and database are deployed.
- Verification or evidence: Verified via 12 PostgreSQL integration tests in `tests/test_api_integration.py` validating read-only session enforcement, response schemas, and equality against `reporting` views.
