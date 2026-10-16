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

Purpose: retain source values and ingestion lineage, including values that may fail validation. Exact string representations (including leading/trailing whitespace) are preserved in all columns and in `raw_payload`. Any surplus fields present in a data row beyond declared columns are preserved in `raw_payload` under the key `_surplus` as an array of strings. Normalization and defect detection are handled by subsequent validation layers.

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
| `validated_at` | `TIMESTAMPTZ` | Yes | Index | Validator timestamp | Batch validation completion timestamp (Phase 2+) |
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

## 4. Implemented Database Tables & Views (Phase 2)

### 4.1 `monitoring.data_quality_issues`
- **Schema / Table:** `monitoring.data_quality_issues`
- **Purpose / Grain:** One row per detected rule violation or warning. Supports multi-issue recording per staged row.
- **Keys / Constraints:** PK (`issue_id`), FK (`batch_id` -> `monitoring.etl_batch_runs(batch_id)` ON DELETE CASCADE), Indexes on `batch_id`, `rule_code`, `severity`, `source_row_id`.

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `issue_id` | `VARCHAR(64)` | No | PK | Generated UUID hex | Unique issue identifier |
| `batch_id` | `VARCHAR(64)` | No | FK, Index | `monitoring.etl_batch_runs` | Lineage batch identifier |
| `entity_type` | `VARCHAR(32)` | No | None | Staged entity name | Entity domain (TRANSACTION, ACCOUNT, CUSTOMER, BRANCH) |
| `source_row_id` | `BIGINT` | Yes | Index | Staging table PK | Staging row identifier (nullable for file-level issues) |
| `source_row_number` | `INT` | No | None | CSV row index | 1-based source row number (0 for file-level issues) |
| `source_file` | `VARCHAR(255)` | No | None | Staging lineage | Source CSV filename |
| `rule_code` | `VARCHAR(64)` | No | Index | Validator constant | Stable, machine-readable rule code |
| `severity` | `VARCHAR(16)` | No | Index | Severity constant | Severity level (ERROR, WARNING, INFO) |
| `reason` | `TEXT` | No | None | Diagnostic explanation | Human-readable explanation of the defect |
| `disposition` | `VARCHAR(32)` | No | None | Disposition constant | Final row disposition (ACCEPTED, REJECTED, WARNED, SKIPPED) |
| `detected_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Detection timestamp |

### 4.2 `quarantine.quarantined_records`
- **Schema / Table:** `quarantine.quarantined_records`
- **Purpose / Grain:** One row per rejected source row. Traceable directly to staging without duplicating raw source data.
- **Keys / Constraints:** PK (`quarantine_id`), FK (`batch_id` -> `monitoring.etl_batch_runs(batch_id)` ON DELETE CASCADE), Indexes on `batch_id`, `source_row_id`, `primary_rule_code`.

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `quarantine_id` | `VARCHAR(64)` | No | PK | Generated UUID hex | Unique quarantine identifier |
| `batch_id` | `VARCHAR(64)` | No | FK, Index | `monitoring.etl_batch_runs` | Lineage batch identifier |
| `entity_type` | `VARCHAR(32)` | No | None | Staged entity name | Entity domain (TRANSACTION, ACCOUNT, etc.) |
| `source_row_id` | `BIGINT` | No | Index | Staging table PK | Relational reference to raw staging record |
| `source_row_number` | `INT` | No | None | CSV row index | Lineage row number in source file |
| `source_file` | `VARCHAR(255)` | No | None | Staging lineage | Source CSV filename |
| `primary_rule_code` | `VARCHAR(64)` | No | Index | First fatal rule code | Primary rule code responsible for quarantine |
| `issue_count` | `INT` | No | Default 1 | Total issues count | Number of discrete issues detected on this row |
| `quarantined_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Quarantine insertion timestamp |

### 4.3 `quarantine.vw_quarantined_transactions`
- **Schema / View:** `quarantine.vw_quarantined_transactions`
- **Purpose / Grain:** Diagnostic view joining `quarantine.quarantined_records` with `staging.stg_transactions` on `source_row_id`. Exposes the full original raw payload, raw amounts, raw timestamps, and metadata without physical data duplication.

## 5. Warehouse Dimensions and Facts (Phase 3)

### 5.1 `warehouse.dim_date`
- **Schema / Table:** `warehouse.dim_date`
- **Purpose / Grain:** Conformed calendar dimension. One row per calendar day (pre-populated 2020 through 2035).
- **Keys / Constraints:** PK (`date_key`), Unique constraint on `full_date`.

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `date_key` | `INT` | No | PK | Formatted `YYYYMMDD` integer | Calendar date surrogate key |
| `full_date` | `DATE` | No | Unique, Index | Date sequence | Calendar date |
| `day_of_month` | `INT` | No | None | Extract day | Day of month (1-31) |
| `day_of_week` | `INT` | No | None | Extract ISO DOW | Day of week (1=Monday, 7=Sunday) |
| `day_name` | `VARCHAR(16)` | No | None | Date format | Full day name (e.g. 'Monday') |
| `week_of_year` | `INT` | No | None | Extract ISO week | ISO week number (1-53) |
| `month_number` | `INT` | No | None | Extract month | Month number (1-12) |
| `month_name` | `VARCHAR(16)` | No | None | Date format | Full month name (e.g. 'January') |
| `quarter_number` | `INT` | No | None | Extract quarter | Quarter (1-4) |
| `year_number` | `INT` | No | None | Extract year | Four-digit calendar year |
| `is_weekend` | `BOOLEAN` | No | None | ISO DOW in (6, 7) | True if Saturday or Sunday |

### 5.2 `warehouse.dim_transaction_type`
- **Schema / Table:** `warehouse.dim_transaction_type`
- **Purpose / Grain:** Conformed dimension for banking transaction classifications. One row per supported transaction type code.
- **Keys / Constraints:** PK (`type_key`), Unique constraint on `transaction_type_code`. Seeded with DEPOSIT, WITHDRAWAL, TRANSFER, PAYMENT, FEE, REVERSAL.

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `type_key` | `SERIAL` | No | PK | Surrogate autoincrement | Dimension primary key |
| `transaction_type_code` | `VARCHAR(32)` | No | Unique | Source code | Business transaction type code |
| `transaction_type_name` | `VARCHAR(64)` | No | None | Standard label | Human-readable transaction type name |
| `transaction_family` | `VARCHAR(32)` | No | None | Accounting classification | Transaction family (CREDIT, DEBIT, TRANSFER, ADJUSTMENT) |

### 5.3 `warehouse.dim_branch`
- **Schema / Table:** `warehouse.dim_branch`
- **Purpose / Grain:** Dimension representing physical/operational bank branch locations. One row per unique branch.
- **Keys / Constraints:** PK (`branch_key`), Unique constraint on `branch_id`, Index on `region`.

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `branch_key` | `SERIAL` | No | PK | Surrogate autoincrement | Dimension primary key |
| `branch_id` | `VARCHAR(64)` | No | Unique | `staging.stg_branches.branch_id` | Natural business branch identifier |
| `branch_name` | `VARCHAR(128)` | No | None | `staging.stg_branches.branch_name` | Branch facility name |
| `region` | `VARCHAR(64)` | No | Index | `staging.stg_branches.region` | Geographic administrative region |
| `created_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Dimension record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Dimension record last updated timestamp |

### 5.4 `warehouse.dim_customer`
- **Schema / Table:** `warehouse.dim_customer`
- **Purpose / Grain:** Customer dimension. One row per unique synthetic banking customer.
- **Keys / Constraints:** PK (`customer_key`), Unique constraint on `customer_id`, Indexes on `customer_segment`, `customer_status`.

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `customer_key` | `SERIAL` | No | PK | Surrogate autoincrement | Dimension primary key |
| `customer_id` | `VARCHAR(64)` | No | Unique | `staging.stg_customers.customer_id` | Natural business customer identifier |
| `customer_segment` | `VARCHAR(32)` | No | Index | `staging.stg_customers.customer_segment` | Customer segment (RETAIL, PREMIUM, etc.) |
| `customer_status` | `VARCHAR(32)` | No | Index | `staging.stg_customers.customer_status` | Customer lifecycle status |
| `created_date` | `DATE` | No | None | Parsed `created_date_raw` | Customer onboarding date |
| `created_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Dimension record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Dimension record last updated timestamp |

### 5.5 `warehouse.dim_account`
- **Schema / Table:** `warehouse.dim_account`
- **Purpose / Grain:** Account dimension. One row per unique banking account, linking to customer and branch dimensions.
- **Keys / Constraints:** PK (`account_key`), Unique constraint on `account_id`, FK (`customer_key` -> `dim_customer`), FK (`branch_key` -> `dim_branch`), Indexes on `customer_key`, `branch_key`, `currency`.

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `account_key` | `SERIAL` | No | PK | Surrogate autoincrement | Dimension primary key |
| `account_id` | `VARCHAR(64)` | No | Unique | `staging.stg_accounts.account_id` | Natural business account identifier |
| `customer_key` | `INT` | No | FK, Index | Lookup `dim_customer` | Foreign key to customer dimension |
| `branch_key` | `INT` | No | FK, Index | Lookup `dim_branch` | Foreign key to branch dimension |
| `account_type` | `VARCHAR(32)` | No | None | `staging.stg_accounts.account_type` | Account product type (CHECKING, SAVINGS) |
| `account_status` | `VARCHAR(32)` | No | None | `staging.stg_accounts.account_status` | Account status (OPEN, CLOSED) |
| `currency` | `VARCHAR(10)` | No | Index | `staging.stg_accounts.currency` | ISO currency code (USD, EUR, GBP) |
| `opened_date` | `DATE` | No | None | Parsed `opened_date_raw` | Account opening date |
| `created_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Dimension record creation timestamp |
| `updated_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Dimension record last updated timestamp |

### 5.6 `warehouse.fact_transactions`
- **Schema / Table:** `warehouse.fact_transactions`
- **Purpose / Grain:** Central transactional fact table. Grain: exactly one row per accepted banking transaction event. Does NOT represent account balances.
- **Keys / Constraints:** PK (`transaction_key`), Unique constraint on `(source_system, transaction_id)`, FKs to `dim_account`, `dim_customer`, `dim_branch`, `dim_date`, `dim_transaction_type`, and `monitoring.etl_batch_runs`. Check constraint `amount > 0.00`. Indexes on foreign keys, status, and currency.

| Column | PostgreSQL type | Nullable? | Key/constraint | Source / derivation | Meaning |
|---|---|---|---|---|---|
| `transaction_key` | `BIGSERIAL` | No | PK | Surrogate autoincrement | Fact transaction primary key |
| `transaction_id` | `VARCHAR(64)` | No | Unique tuple | `staging.stg_transactions.transaction_id` | Source transaction business identifier |
| `source_system` | `VARCHAR(64)` | No | Unique tuple | `staging.stg_transactions.source_system` | Originating source system identifier |
| `account_key` | `INT` | No | FK, Index | Lookup `dim_account` | Foreign key to account dimension |
| `customer_key` | `INT` | No | FK, Index | Lookup via `dim_account` | Foreign key to customer dimension |
| `branch_key` | `INT` | No | FK, Index | Lookup via `dim_account` | Foreign key to branch dimension |
| `date_key` | `INT` | No | FK, Index | Derived from timestamp UTC | Foreign key to calendar date dimension |
| `type_key` | `INT` | No | FK, Index | Lookup `dim_transaction_type` | Foreign key to transaction type dimension |
| `amount` | `NUMERIC(18, 2)` | No | Check (> 0.00) | Parsed `amount_raw` | Transaction monetary value |
| `currency` | `VARCHAR(10)` | No | Index | `staging.stg_transactions.currency` | Transaction ISO currency code |
| `status` | `VARCHAR(32)` | No | Index | `staging.stg_transactions.status` | Transaction status (COMPLETED, PENDING, FAILED) |
| `channel` | `VARCHAR(32)` | No | None | `staging.stg_transactions.channel` | Initiation channel (ONLINE, MOBILE, ATM, BRANCH) |
| `transaction_timestamp` | `TIMESTAMPTZ` | No | None | Parsed `transaction_timestamp_raw` | Exact event occurrence timestamp |
| `source_batch_id` | `VARCHAR(64)` | No | FK, Index | `monitoring.etl_batch_runs.batch_id` | Lineage to ingestion ETL batch |
| `source_row_id` | `BIGINT` | No | None | `staging.stg_transactions.source_row_id` | Lineage to exact staging row |
| `loaded_at` | `TIMESTAMPTZ` | Yes | Default CURRENT_TIMESTAMP | Database default | Warehouse load timestamp |

## 6. Change Control

Every schema change should update the SQL initialization/migration, data-access code, tests, and this dictionary. A phase is not complete if the database schema and dictionary disagree.
