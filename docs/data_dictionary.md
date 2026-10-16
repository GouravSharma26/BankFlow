# BankFlow — Data Dictionary

> Status: planned. This dictionary must be filled with the actual PostgreSQL schema during implementation. Never leave the documented types, nullability, constraints, or descriptions out of sync with the SQL schema.

## 1. Naming and Documentation Rules

For every persisted table, document:

- Schema and table name.
- Business purpose and grain (what one row represents).
- Primary key, foreign keys, unique constraints, and indexes.
- Each column's PostgreSQL type, required/nullable status, default, and semantic meaning.
- Source-to-target mapping where applicable.
- Whether the field contains source data, a derived value, an operational timestamp, or a warehouse surrogate key.

Do not invent customer PII for this educational dataset. Use synthetic opaque IDs.

## 2. Planned Tables

The master `plan.md` describes the intended core tables. The list below is the documentation target; actual names may be finalized in Phase 1 as long as the contract is maintained.

### Staging

- `staging.stg_transactions`
- `staging.stg_accounts`
- `staging.stg_customers`
- `staging.stg_branches`

Purpose: retain source values and ingestion lineage, including values that may fail validation. Exact type choices must preserve malformed raw values sufficiently to produce explainable rejection reasons.

### Monitoring

- `monitoring.etl_batch_runs`
- `monitoring.data_quality_issues`

Purpose: record batch lifecycle, timestamps, counts, reconciliation results, errors, and row-level rule failures.

### Warehouse dimensions

- `warehouse.dim_customer`
- `warehouse.dim_account`
- `warehouse.dim_branch`
- `warehouse.dim_date`
- `warehouse.dim_transaction_type`

Purpose: provide descriptive dimensions with surrogate keys and documented source business identifiers.

### Warehouse fact

- `warehouse.fact_transactions`

Purpose/grain: one accepted transaction event under the defined source event identity policy. It is not an account balance snapshot.

### Reporting

- `reporting` views/queries for daily activity, deposit/withdrawal analysis, branch/channel activity, data quality, and ETL operations.

## 3. Field Inventory Template

Copy one table per implemented database table and replace the placeholders with the true schema:

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `<column_name>` | `<actual_type>` | Yes/No | `<PK/FK/UQ/index/default>` | `<source or expression>` | `<clear definition>` |

## 4. Fact Table Measurement Rules

For the fact table, explicitly document:

- Transaction/event grain.
- Source event key and duplicate/replay policy.
- Dimension foreign keys and unknown-member policy.
- Amount type, sign convention, and currency handling.
- Source transaction type and status semantics.
- Event timestamp and reporting-date semantics.
- Batch/source-row lineage fields.
- Whether the row is an original event, reversal, correction, or another event type.

## 5. Change Control

Every schema change should update the SQL initialization/migration, data-access code, tests, and this dictionary. A phase is not complete if the database schema and dictionary disagree.

_No concrete production schema is documented yet; populate this file as tables are implemented._
