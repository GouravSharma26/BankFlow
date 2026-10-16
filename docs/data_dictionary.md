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

## 3. Implemented Database Tables (Phase 1)

### 3.1 `monitoring.etl_batch_runs`
- **Schema / Table:** `monitoring.etl_batch_runs`
- **Purpose / Grain:** One row per ETL execution batch. Tracks operational lifecycle, timestamps, and row accounting.
- **Keys / Constraints:** PK (`batch_id`).

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `batch_id` | `VARCHAR(64)` | No | PK | Generated UUID string | Unique batch identifier |
| `source_name` | `VARCHAR(255)` | No | None | Caller parameter | Source path or file identifier |
| `started_at` | `TIMESTAMPTZ` | No | None | Application UTC time | Ingestion start timestamp |
| `completed_at` | `TIMESTAMPTZ` | Yes | None | Application UTC time | Ingestion completion timestamp |
| `status` | `VARCHAR(32)` | No | Status enum | State transition | PENDING, RUNNING, SUCCEEDED, SUCCEEDED_WITH_REJECTIONS, FAILED |
| `records_extracted` | `INT` | Yes | Default 0 | Extractor count | Total source rows read from CSVs |
| `records_staged` | `INT` | Yes | Default 0 | Loader count | Total rows inserted into staging tables |
| `records_valid` | `INT` | Yes | Default 0 | Validator count | Valid rows passing contracts (Phase 2+) |
| `records_rejected` | `INT` | Yes | Default 0 | Validator count | Rejected rows quarantined (Phase 2+) |
| `records_inserted` | `INT` | Yes | Default 0 | Loader count | Rows loaded into warehouse facts (Phase 3+) |
| `records_updated` | `INT` | Yes | Default 0 | Loader count | Rows updated in warehouse facts (Phase 3+) |
| `records_skipped` | `INT` | Yes | Default 0 | Loader count | Deduplicated / replayed events skipped (Phase 3+) |
| `reconciliation_status` | `VARCHAR(32)` | Yes | None | Reconciler outcome | Batch reconciliation outcome |
| `error_summary` | `TEXT` | Yes | None | Exception message | High-level failure reason if failed |
| `created_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Row creation timestamp |

### 3.2 `staging.stg_branches`
- **Schema / Table:** `staging.stg_branches`
- **Purpose / Grain:** One row per raw branch record ingested from CSV.
- **Keys / Constraints:** PK (`source_row_id`), FK (`batch_id` -> `monitoring.etl_batch_runs(batch_id)` ON DELETE CASCADE).

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `source_row_id` | `BIGSERIAL` | No | PK | Surrogate autoincrement | Staging row identifier |
| `branch_id` | `VARCHAR(64)` | Yes | None | `branches.csv.branch_id` | Raw synthetic branch identifier |
| `branch_name` | `VARCHAR(128)` | Yes | None | `branches.csv.branch_name` | Raw synthetic branch name |
| `region` | `VARCHAR(64)` | Yes | None | `branches.csv.region` | Raw region code |
| `source_file` | `VARCHAR(255)` | No | None | File metadata | Source filename |
| `batch_id` | `VARCHAR(64)` | No | FK, Index | `monitoring.etl_batch_runs` | Lineage batch identifier |
| `source_row_number` | `INT` | No | None | CSV row index (1-based) | Lineage row number in source file |
| `raw_payload` | `JSONB` | Yes | None | JSON serialization | Complete raw CSV row snapshot |
| `ingested_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Ingestion timestamp |

### 3.3 `staging.stg_customers`
- **Schema / Table:** `staging.stg_customers`
- **Purpose / Grain:** One row per raw customer record ingested from CSV.
- **Keys / Constraints:** PK (`source_row_id`), FK (`batch_id` -> `monitoring.etl_batch_runs(batch_id)` ON DELETE CASCADE).

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `source_row_id` | `BIGSERIAL` | No | PK | Surrogate autoincrement | Staging row identifier |
| `customer_id` | `VARCHAR(64)` | Yes | None | `customers.csv.customer_id` | Raw synthetic customer ID |
| `customer_segment` | `VARCHAR(32)` | Yes | None | `customers.csv.customer_segment` | Raw segment string |
| `created_date_raw` | `VARCHAR(64)` | Yes | None | `customers.csv.created_date` | Preserved raw date string |
| `customer_status` | `VARCHAR(32)` | Yes | None | `customers.csv.customer_status` | Raw customer status |
| `source_file` | `VARCHAR(255)` | No | None | File metadata | Source filename |
| `batch_id` | `VARCHAR(64)` | No | FK, Index | `monitoring.etl_batch_runs` | Lineage batch identifier |
| `source_row_number` | `INT` | No | None | CSV row index (1-based) | Lineage row number in source file |
| `raw_payload` | `JSONB` | Yes | None | JSON serialization | Complete raw CSV row snapshot |
| `ingested_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Ingestion timestamp |

### 3.4 `staging.stg_accounts`
- **Schema / Table:** `staging.stg_accounts`
- **Purpose / Grain:** One row per raw account record ingested from CSV.
- **Keys / Constraints:** PK (`source_row_id`), FK (`batch_id` -> `monitoring.etl_batch_runs(batch_id)` ON DELETE CASCADE).

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `source_row_id` | `BIGSERIAL` | No | PK | Surrogate autoincrement | Staging row identifier |
| `account_id` | `VARCHAR(64)` | Yes | None | `accounts.csv.account_id` | Raw synthetic account ID |
| `customer_id` | `VARCHAR(64)` | Yes | None | `accounts.csv.customer_id` | Raw customer reference |
| `branch_id` | `VARCHAR(64)` | Yes | None | `accounts.csv.branch_id` | Raw branch reference |
| `account_type` | `VARCHAR(32)` | Yes | None | `accounts.csv.account_type` | Raw account type |
| `account_status` | `VARCHAR(32)` | Yes | None | `accounts.csv.account_status` | Raw account status |
| `opened_date_raw` | `VARCHAR(64)` | Yes | None | `accounts.csv.opened_date` | Preserved raw date string |
| `currency` | `VARCHAR(10)` | Yes | None | `accounts.csv.currency` | Raw currency code |
| `source_file` | `VARCHAR(255)` | No | None | File metadata | Source filename |
| `batch_id` | `VARCHAR(64)` | No | FK, Index | `monitoring.etl_batch_runs` | Lineage batch identifier |
| `source_row_number` | `INT` | No | None | CSV row index (1-based) | Lineage row number in source file |
| `raw_payload` | `JSONB` | Yes | None | JSON serialization | Complete raw CSV row snapshot |
| `ingested_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Ingestion timestamp |

### 3.5 `staging.stg_transactions`
- **Schema / Table:** `staging.stg_transactions`
- **Purpose / Grain:** One row per raw transaction event ingested from CSV. Retains raw string representations for amounts and timestamps so malformed rows are preserved for diagnosis.
- **Keys / Constraints:** PK (`source_row_id`), FK (`batch_id` -> `monitoring.etl_batch_runs(batch_id)` ON DELETE CASCADE), Index on `transaction_id`.

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `source_row_id` | `BIGSERIAL` | No | PK | Surrogate autoincrement | Staging row identifier |
| `transaction_id` | `VARCHAR(64)` | Yes | Index | `transactions.csv.transaction_id` | Raw source transaction event ID |
| `account_id` | `VARCHAR(64)` | Yes | None | `transactions.csv.account_id` | Raw account reference |
| `transaction_type` | `VARCHAR(32)` | Yes | None | `transactions.csv.transaction_type` | Raw event type |
| `amount_raw` | `VARCHAR(64)` | Yes | None | `transactions.csv.amount` | Preserved raw amount text |
| `currency` | `VARCHAR(10)` | Yes | None | `transactions.csv.currency` | Raw currency code |
| `transaction_timestamp_raw` | `VARCHAR(64)` | Yes | None | `transactions.csv.transaction_timestamp` | Preserved raw timestamp text |
| `status` | `VARCHAR(32)` | Yes | None | `transactions.csv.status` | Raw transaction status |
| `channel` | `VARCHAR(32)` | Yes | None | `transactions.csv.channel` | Raw channel category |
| `counterparty_account_id` | `VARCHAR(64)` | Yes | None | `transactions.csv.counterparty_account_id` | Optional transfer counterparty |
| `source_system` | `VARCHAR(64)` | Yes | None | `transactions.csv.source_system` | Source system label |
| `source_file` | `VARCHAR(255)` | No | None | File metadata | Source filename |
| `batch_id` | `VARCHAR(64)` | No | FK, Index | `monitoring.etl_batch_runs` | Lineage batch identifier |
| `source_row_number` | `INT` | No | None | CSV row index (1-based) | Lineage row number in source file |
| `raw_payload` | `JSONB` | Yes | None | JSON serialization | Complete raw CSV row snapshot |
| `ingested_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Ingestion timestamp |

## 4. Fact Table Measurement Rules
... (to be populated in Phase 3)

## 5. Change Control

Every schema change should update the SQL initialization/migration, data-access code, tests, and this dictionary. A phase is not complete if the database schema and dictionary disagree.
