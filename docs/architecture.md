# BankFlow — Architecture

> Status: Current through Phase 6 (Portfolio release, hardening, CI, and walk-through verified). Operational batch ETL, dimensional warehouse, monitoring/quarantine, conformed analytical reporting schema, read-only REST API, and CI automation are active.

## 1. Design Goals

- Easy to run and inspect on a student developer's machine.
- Small enough to implement and explain in an interview.
- Data lineage from source file to warehouse fact and quality issue.
- Repeatable batch execution and safe replay.
- Separate source ingestion, validation, transformation, warehouse loading, and analytics.
- Clear failure behavior with actionable logs and reconciliation.
- Synthetic-only data use and no live financial integration.

## 2. Logical Architecture

```text
             +------------------------------+
             | Synthetic Data Generator     |
             | seed + volume + defect cases |
             +---------------+--------------+
                             |
                             v
             +------------------------------+
             | CSV Source Files             |
             | immutable inputs + checksum  |
             +---------------+--------------+
                             |
                             v
             +------------------------------+
             | Extract / Batch Registration |
             +---------------+--------------+
                             |
                             v
             +------------------------------+
             | PostgreSQL Staging           |
             | source rows + source lineage |
             +---------------+--------------+
                             |
               +-------------+-------------+
               |                           |
               v                           v
  +--------------------------+   +--------------------------+
  | Validation and Transform |-->| Quality Issues/Quarantine|
  +-------------+------------+   +--------------------------+
                |
                v
  +--------------------------+
  | PostgreSQL Warehouse     |
  | dimensions + fact table  |
  +-------------+------------+
                |
                v
  +--------------------------+
  | Reporting Views (SQL)    |
  +-------------+------------+
                |
       +--------+--------+
       |                 |
       v                 v
+--------------+   +-------------------------------+
| Python CLI   |   | Read-Only FastAPI Service     |
| bankflow rpt |   | bankflow serve (least-priv.)  |
+--------------+   +---------------+---------------+
                                   |
                                   v
                   +-------------------------------+
                   | Lovable Analytics Console     |
                   | (Web App / Demo Mode Boundary)|
                   +-------------------------------+

Operational metadata: batch state, counts, timings, reconciliation,
and error summaries are persisted separately and linked by batch ID.
```

## 3. Layers and Responsibilities

### 3.1 Generator

Creates synthetic customers, accounts, branches, and transaction event files. Must support fixed-seed generation, configurable volume/date ranges, and individually testable defect scenarios. Generated records must be labelled as synthetic and avoid unnecessary personally identifying fields.

### 3.2 Extraction

Checks file readability, encoding, required headers, and file-level structure. Captures source filename, source row number, batch ID, ingestion time, and a file fingerprint where appropriate. File-level defects may stop the file; row-level defects should be preserved for validation when parsing permits.

### 3.3 Staging

Retains input values in a representation that allows malformed values to be diagnosed. Do not coerce away the raw text of malformed amounts/timestamps before the quality issue is recorded. Staging records must be traceable to a specific batch and row.

### 3.4 Validation and Transformation

Validation assigns stable rule codes and outcomes. Transformation runs only for records allowed by the documented quality policy. Normalization mappings must be explicit, deterministic, unit-tested, and documented in `data_contract.md`.

### 3.5 Monitoring and Quarantine

A batch-run record should capture status, timestamps, counts, and error summary. Quality issue records link to batch/source row and identify the violated rule. Row-level rejection is distinct from a system-level batch failure. Batch success is not recorded before the relevant database transaction commits.

### 3.6 Warehouse

Use a dimensional design with a central transaction fact and descriptive dimensions. The transaction fact grain is one accepted source transaction event as defined by the data contract—not an account balance snapshot. Use surrogate dimension keys while preserving source business IDs for lineage and idempotency.

### 3.7 Reporting

The reporting layer resides in the dedicated `reporting` PostgreSQL schema and provides conformed analytical views built directly over the star schema warehouse, monitoring, and quarantine tables. These views establish the single authoritative source of truth for downstream reports, CLI utilities, and the dashboard API.

Implemented views:
- `reporting.v_daily_transaction_summary`: Daily volume, gross event value, and completed/failed counts by UTC date and currency.
- `reporting.v_deposit_withdrawal_analysis`: Completed cash-flow activity comparing deposits vs withdrawals with explicit completed-status filtering.
- `reporting.v_branch_channel_activity`: Channel and branch distribution of transaction events and completed volume.
- `reporting.v_transaction_type_mix`: Portfolio breakdown across standard transaction types, event share, and value share.
- `reporting.v_data_quality_summary`: Multi-issue accounting distinguishing distinct quality defects, affected source rows, and impacted batches.
- `reporting.v_pipeline_execution_health`: Batch execution status, lifecycle duration (seconds), validation efficiency, and reconciliation outcomes.
- `reporting.v_quarantine_inventory`: Quarantined record inventory grouped by entity, primary rule code, and batch.
- `reporting.v_transaction_details`: Conformed fact-to-dimension detail view for transaction exploration, strictly isolating raw staging payloads and credentials.

Key reporting architectural rules:
- **Currency Isolation**: All monetary amounts are strictly aggregated per currency; no cross-currency summation or synthetic FX conversion is permitted.
- **Gross Event Amounts**: The fact table represents discrete transaction events, not running account balances. All transaction amounts are positive gross values.
- **UTC Date Standardization**: Reporting dates are derived directly from the immutable warehouse date dimension key (`dim_date.calendar_date`), preventing session timezone drift.
- **Status & Reversal Explicitness**: Completed-event metrics filter strictly on `COMPLETED` status; reversals (`REVERSAL` transaction type or `REVERSED` status) are never naively subtracted as negative facts without explicit reporting models.
- **Zero-Mutation Guarantee**: Analytical queries and reporting views are strictly read-only and have zero side-effects on staging or warehouse data.

### 3.8 Dashboard API & Frontend Integration

The dashboard integration layer connects the conformed `reporting` schema to the external web console (`https://bankflow-analytics-console.lovable.app/`):

- **FastAPI Read-Only Backend**: A lightweight, versioned REST API (`src/bankflow/api`) under `/api/v1` exposing the 8 reporting views and health status. Packaged as an optional extra (`pip install -e ".[api]"`).
- **Least-Privilege Database Role**: A dedicated PostgreSQL role (`bankflow_reporting_user`) with `SELECT` grant exclusively on `reporting.*`. Staging, quarantine, monitoring, and warehouse tables cannot be queried directly or mutated.
- **Application Defense-in-Depth**: Every database session is explicitly configured with `readonly=True`, `autocommit=True`, and a 5-second `statement_timeout`.
- **CORS Configuration**: Restricts browser cross-origin requests to configured origins (`https://bankflow-analytics-console.lovable.app`, local dev hosts).
- **Zero-Secret Contract**: The API never accepts or returns credentials, connection strings, or raw customer data. The frontend is configured solely via a public base URL environment variable (`VITE_BANKFLOW_API_BASE_URL`).
- **Demo Mode Boundary**: The hosted Lovable console operates in synthetic Demo Mode by default until pointed to an active, deployed BankFlow API instance.

## 4. Implemented Data Schemas

The database uses dedicated PostgreSQL schemas to enforce separation of concerns:

- `staging` — raw values, file headers, and row-level lineage.
- `monitoring` — ETL batch runs, execution metrics, reconciliation results, and data quality issues.
- `quarantine` — quarantined records and relational views linking back to raw staging without data duplication.
- `warehouse` — dimensional star schema (conformed dimensions and fact transactions).
- `reporting` — conformed analytical views providing the authoritative metric layer for reports and dashboards.

## 5. Batch Lifecycle

Planned states:

```text
PENDING -> RUNNING -> SUCCEEDED
                    -> SUCCEEDED_WITH_REJECTIONS
                    -> FAILED
```

A row-rejection policy may permit the batch to complete with rejections; infrastructure/file-structure failures should fail the batch. The exact state transition rules must be unit/integration tested. No success status should precede commit of warehouse changes.

## 6. Idempotency and Transaction Boundaries

- Define one stable source event identity, typically a source-system identifier plus transaction event ID if multi-source support is included.
- Enforce uniqueness in PostgreSQL.
- Use `INSERT ... ON CONFLICT` or equivalent safe semantics as appropriate, but document whether conflicts are skipped, updated, or treated as errors.
- Do not treat a legitimate reversal as an accidental duplicate solely because its amount/account resembles another event.
- Load dimension references before facts or use a documented unresolved-dimension strategy.
- Use explicit transactions for logically related warehouse changes and test rollback behavior.
- Record inserted, updated, skipped, and rejected outcomes separately.

## 7. Component Structure (Target)

```text
src/bankflow/
├── __init__.py
├── __main__.py              # CLI entry point
├── config.py                # settings/env parsing
├── db.py                    # connection/session helpers
├── generator/               # synthetic entity/event generation
├── extraction/              # CSV parsing and file-level contract checks
├── validation/              # row/domain/reference rules
├── transformation/          # normalization and mapping
├── loading/                 # staging/warehouse writes
├── monitoring/              # batch status, quality, reconciliation
├── analytics/                # callable report queries if useful
└── etl.py                    # orchestration only
```

This is a target, not a requirement to create empty modules immediately. Introduce each module when the current phase needs it. Avoid circular imports and keep database I/O out of pure validation functions where practical.

## 8. Operational Flow

Expected high-level CLI flow (final exact syntax must be verified and documented when implemented):

1. Generate synthetic source files.
2. Initialize database schema.
3. Run ETL against a source file/directory.
4. Inspect a batch status and its quality issues.
5. Run reconciliation and analytics queries.
6. Execute tests against a dedicated test database.

## 9. Failure Behavior

- File-level schema/encoding errors: fail the file/batch clearly and record failure details.
- Row-level data errors: preserve the row as far as possible, record stable quality issues, and reject/quarantine according to policy.
- Database transaction failure: roll back the affected transaction scope, mark the batch failed where possible, and provide a useful error summary.
- Retry/replay: safe and deterministic; no duplicate facts.
- Reporting failure: must not modify warehouse data.

## 10. Architecture Decision Triggers

Before adding a new service, library, schema, or deployment environment, state the problem it solves, simplest alternative, testing impact, operational cost, and what would become more complex. Keep the MVP local and boring until correctness is established.
