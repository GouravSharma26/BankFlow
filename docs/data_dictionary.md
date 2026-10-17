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

## 6. Implemented Reporting Views (Phase 4)

### 6.1 `reporting.v_daily_transaction_summary`
- **Schema / View:** `reporting.v_daily_transaction_summary`
- **Purpose / Grain:** Aggregated transaction metrics per calendar reporting date and currency. Grain: (`reporting_date`, `currency`).
- **Underlying Tables:** `warehouse.fact_transactions`, `warehouse.dim_date`.

| Column | PostgreSQL type | Nullable? | Source / derivation | Meaning |
|---|---|---|---|---|
| `date_key` | `INT` | No | `dim_date.date_key` | Calendar date key (YYYYMMDD) |
| `reporting_date` | `DATE` | No | `dim_date.full_date` | Calendar date in UTC |
| `year_number` | `INT` | No | `dim_date.year_number` | Calendar year |
| `month_number` | `INT` | No | `dim_date.month_number` | Calendar month number (1-12) |
| `month_name` | `VARCHAR(16)` | No | `dim_date.month_name` | Full month name |
| `day_name` | `VARCHAR(16)` | No | `dim_date.day_name` | Day of week name |
| `is_weekend` | `BOOLEAN` | No | `dim_date.is_weekend` | True if Saturday or Sunday |
| `currency` | `VARCHAR(10)` | No | `fact_transactions.currency` | ISO currency code |
| `total_transaction_count` | `BIGINT` | No | `COUNT(*)` | Total transaction event count |
| `completed_transaction_count` | `BIGINT` | No | `COUNT(*) FILTER (WHERE status = 'COMPLETED')` | Settled transaction event count |
| `pending_transaction_count` | `BIGINT` | No | `COUNT(*) FILTER (WHERE status = 'PENDING')` | Pending transaction count |
| `failed_transaction_count` | `BIGINT` | No | `COUNT(*) FILTER (WHERE status = 'FAILED')` | Failed transaction count |
| `reversed_transaction_count` | `BIGINT` | No | `COUNT(*) FILTER (WHERE status = 'REVERSED')` | Reversed transaction count |
| `active_accounts` | `BIGINT` | No | `COUNT(DISTINCT account_key)` | Unique transacting accounts |
| `active_customers` | `BIGINT` | No | `COUNT(DISTINCT customer_key)` | Unique transacting customers |
| `gross_transaction_amount` | `NUMERIC(18, 2)` | No | `SUM(amount)` | Gross monetary volume |
| `completed_gross_amount` | `NUMERIC(18, 2)` | No | `COALESCE(SUM(amount) FILTER (...), 0.00)` | Completed gross monetary volume |

### 6.2 `reporting.v_deposit_withdrawal_analysis`
- **Schema / View:** `reporting.v_deposit_withdrawal_analysis`
- **Purpose / Grain:** Deposit and withdrawal volume and value comparison per date and currency. Grain: (`reporting_date`, `currency`).
- **Underlying Tables:** `warehouse.fact_transactions`, `warehouse.dim_date`, `warehouse.dim_transaction_type`.

| Column | PostgreSQL type | Nullable? | Source / derivation | Meaning |
|---|---|---|---|---|
| `date_key` | `INT` | No | `dim_date.date_key` | Calendar date key |
| `reporting_date` | `DATE` | No | `dim_date.full_date` | Calendar date in UTC |
| `currency` | `VARCHAR(10)` | No | `fact_transactions.currency` | ISO currency code |
| `deposit_count` | `BIGINT` | No | `COUNT(*) FILTER (type = 'DEPOSIT')` | Total deposit count |
| `deposit_gross_amount` | `NUMERIC(18, 2)` | No | `SUM(amount) FILTER (type = 'DEPOSIT')` | Total deposit gross amount |
| `completed_deposit_count` | `BIGINT` | No | `COUNT(*) FILTER (type = 'DEPOSIT' AND COMPLETED)` | Completed deposit count |
| `completed_deposit_gross_amount` | `NUMERIC(18, 2)` | No | `SUM(amount) FILTER (type = 'DEPOSIT' AND COMPLETED)` | Completed deposit gross amount |
| `withdrawal_count` | `BIGINT` | No | `COUNT(*) FILTER (type = 'WITHDRAWAL')` | Total withdrawal count |
| `withdrawal_gross_amount` | `NUMERIC(18, 2)` | No | `SUM(amount) FILTER (type = 'WITHDRAWAL')` | Total withdrawal gross amount |
| `completed_withdrawal_count` | `BIGINT` | No | `COUNT(*) FILTER (type = 'WITHDRAWAL' AND COMPLETED)` | Completed withdrawal count |
| `completed_withdrawal_gross_amount` | `NUMERIC(18, 2)` | No | `SUM(amount) FILTER (type = 'WITHDRAWAL' AND COMPLETED)` | Completed withdrawal gross amount |
| `reversal_count` | `BIGINT` | No | `COUNT(*) FILTER (type = 'REVERSAL')` | Reversal event count |
| `reversal_gross_amount` | `NUMERIC(18, 2)` | No | `SUM(amount) FILTER (type = 'REVERSAL')` | Reversal gross amount |

### 6.3 `reporting.v_branch_channel_activity`
- **Schema / View:** `reporting.v_branch_channel_activity`
- **Purpose / Grain:** Activity grouped by operational branch, region, initiation channel, and currency. Grain: (`region`, `branch_id`, `channel`, `currency`).
- **Underlying Tables:** `warehouse.fact_transactions`, `warehouse.dim_branch`.

| Column | PostgreSQL type | Nullable? | Source / derivation | Meaning |
|---|---|---|---|---|
| `region` | `VARCHAR(64)` | No | `dim_branch.region` | Branch geographical region |
| `branch_id` | `VARCHAR(64)` | No | `dim_branch.branch_id` | Branch business identifier |
| `branch_name` | `VARCHAR(128)` | No | `dim_branch.branch_name` | Branch facility name |
| `channel` | `VARCHAR(32)` | No | `fact_transactions.channel` | Initiation channel |
| `currency` | `VARCHAR(10)` | No | `fact_transactions.currency` | ISO currency code |
| `total_transaction_count` | `BIGINT` | No | `COUNT(*)` | Total transaction count |
| `completed_transaction_count` | `BIGINT` | No | `COUNT(*) FILTER (COMPLETED)` | Completed transaction count |
| `distinct_accounts` | `BIGINT` | No | `COUNT(DISTINCT account_key)` | Unique transacting accounts |
| `distinct_customers` | `BIGINT` | No | `COUNT(DISTINCT customer_key)` | Unique transacting customers |
| `gross_transaction_amount` | `NUMERIC(18, 2)` | No | `SUM(amount)` | Total gross transaction amount |
| `completed_gross_amount` | `NUMERIC(18, 2)` | No | `SUM(amount) FILTER (COMPLETED)` | Completed gross transaction amount |

### 6.4 `reporting.v_transaction_type_mix`
- **Schema / View:** `reporting.v_transaction_type_mix`
- **Purpose / Grain:** Breakdown by transaction type code, category, and currency. Grain: (`transaction_type_code`, `currency`).
- **Underlying Tables:** `warehouse.fact_transactions`, `warehouse.dim_transaction_type`.

| Column | PostgreSQL type | Nullable? | Source / derivation | Meaning |
|---|---|---|---|---|
| `transaction_type_code` | `VARCHAR(32)` | No | `dim_transaction_type.transaction_type_code` | Type business code |
| `transaction_type_name` | `VARCHAR(64)` | No | `dim_transaction_type.transaction_type_name` | Type display label |
| `transaction_family` | `VARCHAR(32)` | No | `dim_transaction_type.transaction_family` | Family (CREDIT, DEBIT, TRANSFER, ADJUSTMENT) |
| `currency` | `VARCHAR(10)` | No | `fact_transactions.currency` | ISO currency code |
| `total_transaction_count` | `BIGINT` | No | `COUNT(*)` | Total transaction count |
| `completed_transaction_count` | `BIGINT` | No | `COUNT(*) FILTER (COMPLETED)` | Completed transaction count |
| `failed_transaction_count` | `BIGINT` | No | `COUNT(*) FILTER (FAILED)` | Failed transaction count |
| `pending_transaction_count` | `BIGINT` | No | `COUNT(*) FILTER (PENDING)` | Pending transaction count |
| `reversed_transaction_count` | `BIGINT` | No | `COUNT(*) FILTER (REVERSED)` | Reversed transaction count |
| `gross_transaction_amount` | `NUMERIC(18, 2)` | No | `SUM(amount)` | Gross transaction amount |
| `completed_gross_amount` | `NUMERIC(18, 2)` | No | `SUM(amount) FILTER (COMPLETED)` | Completed gross transaction amount |

### 6.5 `reporting.v_data_quality_summary`
- **Schema / View:** `reporting.v_data_quality_summary`
- **Purpose / Grain:** Data-quality violations summarized by rule code, severity, and disposition. Grain: (`rule_code`, `severity`, `disposition`).
- **Underlying Tables:** `monitoring.data_quality_issues`.

| Column | PostgreSQL type | Nullable? | Source / derivation | Meaning |
|---|---|---|---|---|
| `rule_code` | `VARCHAR(64)` | No | `data_quality_issues.rule_code` | Violated contract rule code |
| `severity` | `VARCHAR(16)` | No | `data_quality_issues.severity` | ERROR, WARNING, INFO |
| `disposition` | `VARCHAR(32)` | No | `data_quality_issues.disposition` | REJECTED, ACCEPTED, SKIPPED |
| `issue_count` | `BIGINT` | No | `COUNT(*)` | Total issue instances recorded |
| `affected_source_rows` | `BIGINT` | No | `COUNT(DISTINCT source_row_id)` | Unique source rows affected |
| `affected_batches` | `BIGINT` | No | `COUNT(DISTINCT batch_id)` | Unique ETL batches affected |

### 6.6 `reporting.v_pipeline_execution_health`
- **Schema / View:** `reporting.v_pipeline_execution_health`
- **Purpose / Grain:** Operational health, row accounting, duration, and reconciliation status per batch. Grain: (`batch_id`).
- **Underlying Tables:** `monitoring.etl_batch_runs`.

| Column | PostgreSQL type | Nullable? | Source / derivation | Meaning |
|---|---|---|---|---|
| `batch_id` | `VARCHAR(64)` | No | `etl_batch_runs.batch_id` | Unique batch identifier |
| `source_name` | `VARCHAR(255)` | No | `etl_batch_runs.source_name` | Input dataset path / identifier |
| `started_at` | `TIMESTAMPTZ` | No | `etl_batch_runs.started_at` | Ingestion start timestamp |
| `completed_at` | `TIMESTAMPTZ` | Yes | `etl_batch_runs.completed_at` | Ingestion completion timestamp |
| `duration_seconds` | `NUMERIC` | Yes | `EXTRACT(EPOCH FROM (completed - started))` | Execution time in seconds |
| `status` | `VARCHAR(32)` | No | `etl_batch_runs.status` | Batch lifecycle status |
| `records_extracted` | `INT` | Yes | `etl_batch_runs.records_extracted` | Source CSV rows discovered |
| `records_staged` | `INT` | Yes | `etl_batch_runs.records_staged` | Staged rows inserted |
| `records_valid` | `INT` | Yes | `etl_batch_runs.records_valid` | Staged rows passing validation |
| `records_rejected` | `INT` | Yes | `etl_batch_runs.records_rejected` | Staged rows quarantined |
| `records_inserted` | `INT` | Yes | `etl_batch_runs.records_inserted` | New facts loaded |
| `records_updated` | `INT` | Yes | `etl_batch_runs.records_updated` | Updated facts |
| `records_skipped` | `INT` | Yes | `etl_batch_runs.records_skipped` | Replay duplicates skipped |
| `rejection_rate_pct` | `NUMERIC(5, 2)` | No | `ROUND(rejected / staged * 100, 2)` | Percentage of staged rows quarantined |
| `reconciliation_status` | `VARCHAR(32)` | Yes | `etl_batch_runs.reconciliation_status` | RECONCILED / UNRECONCILED |
| `error_summary` | `TEXT` | Yes | `etl_batch_runs.error_summary` | Failure explanation if any |

### 6.7 `reporting.v_quarantine_inventory`
- **Schema / View:** `reporting.v_quarantine_inventory`
- **Purpose / Grain:** Quarantined records inventory by batch, entity type, and primary rule code. Grain: (`batch_id`, `entity_type`, `primary_rule_code`).
- **Underlying Tables:** `quarantine.quarantined_records`.

| Column | PostgreSQL type | Nullable? | Source / derivation | Meaning |
|---|---|---|---|---|
| `batch_id` | `VARCHAR(64)` | No | `quarantined_records.batch_id` | Lineage batch identifier |
| `entity_type` | `VARCHAR(32)` | No | `quarantined_records.entity_type` | BRANCH, CUSTOMER, ACCOUNT, TRANSACTION |
| `primary_rule_code` | `VARCHAR(64)` | No | `quarantined_records.primary_rule_code` | Primary rejection rule code |
| `quarantined_rows` | `BIGINT` | No | `COUNT(*)` | Number of quarantined rows |
| `recorded_issue_count` | `BIGINT` | No | `SUM(issue_count)` | Sum of quality issues on quarantined rows |
| `first_quarantined_at` | `TIMESTAMPTZ` | Yes | `MIN(quarantined_at)` | Earliest quarantine timestamp |
| `last_quarantined_at` | `TIMESTAMPTZ` | Yes | `MAX(quarantined_at)` | Latest quarantine timestamp |

### 6.8 `reporting.v_transaction_details`
- **Schema / View:** `reporting.v_transaction_details`
- **Purpose / Grain:** Detailed conformed transaction facts joined with dimensional attributes for the dashboard Transactions explorer. Exposes only analytical attributes; strictly isolates raw staging payloads, internal keys, and credentials. Grain: One row per loaded fact transaction (`transaction_key`).
- **Underlying Tables:** `warehouse.fact_transactions`, `warehouse.dim_date`, `warehouse.dim_transaction_type`, `warehouse.dim_branch`, `warehouse.dim_customer`, `warehouse.dim_account`.

| Column | PostgreSQL type | Nullable? | Source / derivation | Meaning |
|---|---|---|---|---|
| `transaction_key` | `BIGINT` | No | `fact_transactions.transaction_key` | Fact transaction surrogate primary key |
| `transaction_id` | `VARCHAR(64)` | No | `fact_transactions.transaction_id` | Source transaction identifier |
| `transaction_timestamp` | `TIMESTAMPTZ` | No | `fact_transactions.transaction_timestamp` | Event timestamp in UTC |
| `reporting_date` | `DATE` | No | `dim_date.full_date` | Conformed UTC reporting date |
| `transaction_type` | `VARCHAR(32)` | No | `dim_transaction_type.transaction_type_code` | Transaction business type |
| `transaction_family` | `VARCHAR(32)` | No | `dim_transaction_type.transaction_family` | Accounting family classification |
| `amount` | `NUMERIC(18, 2)` | No | `fact_transactions.amount` | Positive gross transaction amount |
| `currency` | `VARCHAR(10)` | No | `fact_transactions.currency` | ISO currency code |
| `status` | `VARCHAR(32)` | No | `fact_transactions.status` | Transaction status (COMPLETED, PENDING, FAILED, REVERSED) |
| `channel` | `VARCHAR(32)` | No | `fact_transactions.channel` | Initiation channel (ONLINE, MOBILE, ATM, BRANCH) |
| `branch_id` | `VARCHAR(64)` | No | `dim_branch.branch_id` | Originating branch identifier |
| `branch_name` | `VARCHAR(128)` | No | `dim_branch.branch_name` | Originating branch facility name |
| `region` | `VARCHAR(64)` | No | `dim_branch.region` | Branch administrative region |
| `customer_id` | `VARCHAR(64)` | No | `dim_customer.customer_id` | Transacting customer identifier |
| `customer_segment` | `VARCHAR(32)` | No | `dim_customer.customer_segment` | Customer segment (RETAIL, PREMIUM, etc.) |
| `account_id` | `VARCHAR(64)` | No | `dim_account.account_id` | Primary transacting account identifier |
| `account_type` | `VARCHAR(32)` | No | `dim_account.account_type` | Account type (CHECKING, SAVINGS) |
| `batch_id` | `VARCHAR(64)` | No | `fact_transactions.batch_id` | Ingestion batch lineage identifier |

## 7. Change Control

Every schema change should update the SQL initialization/migration, data-access code, tests, and this dictionary. A phase is not complete if the database schema and dictionary disagree.
