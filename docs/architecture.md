# BankFlow — Architecture

> Status: planned architecture. Update this document when implementation establishes or changes concrete interfaces. Do not treat planned components as already implemented.

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
  | Reporting Views / SQL    |
  +-------------+------------+
                |
                v
  +--------------------------+
  | Dashboard / CSV Reports  |
  +--------------------------+

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

Reporting SQL or views should be the authoritative definition of dashboard metrics. Group or filter by currency unless an explicit FX conversion model is implemented. Clearly define status semantics and whether the metric counts events, value of events, or account balances.

## 4. Planned Data Schemas

Prefer PostgreSQL schemas such as:

- `staging` — raw values and source lineage.
- `monitoring` — ETL batch runs and data quality issues.
- `quarantine` — quarantined records and relational views linking back to raw staging without data duplication.
- `warehouse` — dimensions and fact table.
- `reporting` — views intended for analytics/dashboard usage.

These are logical boundaries. They can be created as separate PostgreSQL schemas or adapted to consistent table prefixes if the implementation has a justified reason. Document deviations before adding them.

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
