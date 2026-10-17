# BankFlow — Metric Definitions & Reporting Contract

> **Status:** Verified reporting contract (Phase 4).
> This document defines the exact formulas, grains, dimensions, status filtering, currency semantics, null handling, and expected behaviors implemented in `reporting` schema views and SQL queries.
> All analytics consumers (SQL reports, CLI commands, and future Phase 5 BI dashboards) must adhere to these definitions without alteration.

---

## 1. Foundational Analytical Principles

1. **Transaction Events vs. Account Balances:**
   - The warehouse fact table (`warehouse.fact_transactions`) models **discrete transaction events**, not point-in-time account balance snapshots or ledger statements.
   - Summing transaction event amounts represents **gross transaction volume/flow**, never net account balance, cash flow, bank revenue, or net profit.
   - Event amounts are strictly non-negative (`amount > 0.00`). Signs (positive/negative) are not assigned to amounts.

2. **Currency Isolation (No Cross-Currency Aggregation):**
   - Every metric involving monetary sums **MUST group by or filter on `currency`**.
   - Summing amounts across different currencies (e.g. USD + EUR + GBP) is strictly prohibited. No implicit or arbitrary FX conversion is performed.

3. **Reporting Date and UTC Timezone:**
   - All reporting dates (`reporting_date` / `date_key`) are conformed to **UTC calendar dates**, derived directly from `transaction_timestamp AT TIME ZONE 'UTC'`.
   - Analytical queries and reporting views join to `warehouse.dim_date` on `date_key`, ensuring date derivation is deterministic and independent of client database session timezones.

4. **Status Inclusions and Exclusion Rules:**
   - Supported transaction statuses: `COMPLETED`, `PENDING`, `FAILED`, `REVERSED`.
   - Metrics are explicitly divided into:
     - **Total / All-Event metrics:** Capture total operational event arrival (`COUNT(*)`, `SUM(amount)`).
     - **Completed-Event metrics:** Filter strictly on `status = 'COMPLETED'`.
   - Completed-event metrics represent settled banking actions and must never be conflated with all-event metrics.

5. **Treatment of Reversals & Adjustments:**
   - Supported transaction types: `DEPOSIT` (Credit), `WITHDRAWAL` (Debit), `TRANSFER` (Transfer), `PAYMENT` (Debit), `FEE` (Debit), `REVERSAL` (Adjustment).
   - `REVERSAL` events represent distinct compensating transaction events. Under the gross event model, reversals are reported as their own category (`reversal_count`, `reversal_gross_amount`) and **do not subtract from or decrement** deposit or withdrawal sums.

6. **Empty-Result & Division-by-Zero Behavior:**
   - All ratio/percentage metrics use SQL `NULLIF(denominator, 0)` wrapped in `COALESCE(..., 0.00)` to ensure safe zero-division handling.
   - When no matching records exist for a filter, aggregate queries return zero rows or `0.00` / `0` counts rather than `NULL` or run-time division errors.

7. **Count Disambiguation (Events vs. Rows vs. Issues vs. Accounts):**
   - **Transaction Event Count:** Count of committed warehouse facts (`COUNT(*)` on `fact_transactions`).
   - **Staged Row Count:** Total rows loaded into staging tables (`records_staged`).
   - **Rejected Row Count:** Distinct source staging rows rejected and quarantined (`records_rejected` / `quarantined_rows`).
   - **Quality Issue Count:** Number of distinct rule violation entries (`COUNT(*)` on `data_quality_issues`). A single rejected row may record multiple distinct quality issues.
   - **Active Account / Customer Count:** Distinct dimension entities participating in events (`COUNT(DISTINCT account_key)`, `COUNT(DISTINCT customer_key)`).

---

## 2. Analytical Metric Specifications

### 2.1 Daily Transaction Summary (`reporting.v_daily_transaction_summary`)

- **Grain:** One row per `reporting_date` (`dim_date.full_date`) and `currency`.
- **Source Layer:** `warehouse.fact_transactions` joined to `warehouse.dim_date`.

| Metric Name | SQL Formula / Definition | Output Units | Status Inclusion | Business Meaning |
|---|---|---|---|---|
| `total_transaction_count` | `COUNT(*)` | Integer (events) | All (`COMPLETED`, `PENDING`, `FAILED`, `REVERSED`) | Total transaction volume initiated on that date |
| `completed_transaction_count` | `COUNT(*) FILTER (WHERE status = 'COMPLETED')` | Integer (events) | `COMPLETED` only | Successfully settled transactions |
| `pending_transaction_count` | `COUNT(*) FILTER (WHERE status = 'PENDING')` | Integer (events) | `PENDING` only | Transactions awaiting settlement |
| `failed_transaction_count` | `COUNT(*) FILTER (WHERE status = 'FAILED')` | Integer (events) | `FAILED` only | Aborted or rejected processing attempts |
| `reversed_transaction_count` | `COUNT(*) FILTER (WHERE status = 'REVERSED')` | Integer (events) | `REVERSED` only | Transactions subsequently marked reversed |
| `active_accounts` | `COUNT(DISTINCT f.account_key)` | Integer (accounts) | All statuses | Unique accounts transacting on that date |
| `active_customers` | `COUNT(DISTINCT f.customer_key)` | Integer (customers) | All statuses | Unique customers transacting on that date |
| `gross_transaction_amount` | `SUM(f.amount)::NUMERIC(18, 2)` | Decimal (money in currency) | All statuses | Gross event amount transacted |
| `completed_gross_amount` | `COALESCE(SUM(amount) FILTER (WHERE status = 'COMPLETED'), 0.00)::NUMERIC(18, 2)` | Decimal (money in currency) | `COMPLETED` only | Gross amount of successfully settled transactions |

---

### 2.2 Deposit versus Withdrawal Analysis (`reporting.v_deposit_withdrawal_analysis`)

- **Grain:** One row per `reporting_date` (`dim_date.full_date`) and `currency`.
- **Source Layer:** `warehouse.fact_transactions` joined to `warehouse.dim_date` and `warehouse.dim_transaction_type`.

| Metric Name | SQL Formula / Definition | Output Units | Inclusions / Exclusions |
|---|---|---|---|
| `deposit_count` | `COUNT(*) FILTER (WHERE t.transaction_type_code = 'DEPOSIT')` | Integer (events) | `DEPOSIT` type, all statuses |
| `deposit_gross_amount` | `COALESCE(SUM(amount) FILTER (WHERE type = 'DEPOSIT'), 0.00)::NUMERIC(18, 2)` | Decimal (currency) | `DEPOSIT` type, all statuses |
| `completed_deposit_count` | `COUNT(*) FILTER (WHERE type = 'DEPOSIT' AND status = 'COMPLETED')` | Integer (events) | `DEPOSIT` type, `COMPLETED` only |
| `completed_deposit_gross_amount` | `COALESCE(SUM(amount) FILTER (WHERE type = 'DEPOSIT' AND status = 'COMPLETED'), 0.00)::NUMERIC(18, 2)` | Decimal (currency) | `DEPOSIT` type, `COMPLETED` only |
| `withdrawal_count` | `COUNT(*) FILTER (WHERE type = 'WITHDRAWAL')` | Integer (events) | `WITHDRAWAL` type, all statuses |
| `withdrawal_gross_amount` | `COALESCE(SUM(amount) FILTER (WHERE type = 'WITHDRAWAL'), 0.00)::NUMERIC(18, 2)` | Decimal (currency) | `WITHDRAWAL` type, all statuses |
| `completed_withdrawal_count` | `COUNT(*) FILTER (WHERE type = 'WITHDRAWAL' AND status = 'COMPLETED')` | Integer (events) | `WITHDRAWAL` type, `COMPLETED` only |
| `completed_withdrawal_gross_amount` | `COALESCE(SUM(amount) FILTER (WHERE type = 'WITHDRAWAL' AND status = 'COMPLETED'), 0.00)::NUMERIC(18, 2)` | Decimal (currency) | `WITHDRAWAL` type, `COMPLETED` only |
| `reversal_count` | `COUNT(*) FILTER (WHERE type = 'REVERSAL')` | Integer (events) | `REVERSAL` type, all statuses |
| `reversal_gross_amount` | `COALESCE(SUM(amount) FILTER (WHERE type = 'REVERSAL'), 0.00)::NUMERIC(18, 2)` | Decimal (currency) | `REVERSAL` type, all statuses |

---

### 2.3 Branch and Channel Activity (`reporting.v_branch_channel_activity`)

- **Grain:** One row per `region`, `branch_id`, `branch_name`, `channel`, and `currency`.
- **Source Layer:** `warehouse.fact_transactions` joined to `warehouse.dim_branch`.

| Metric Name | SQL Formula / Definition | Output Units | Meaning |
|---|---|---|---|
| `total_transaction_count` | `COUNT(*)` | Integer (events) | Total transactions at facility/channel |
| `completed_transaction_count` | `COUNT(*) FILTER (WHERE status = 'COMPLETED')` | Integer (events) | Settled transactions at facility/channel |
| `distinct_accounts` | `COUNT(DISTINCT f.account_key)` | Integer (accounts) | Unique accounts initiating transactions |
| `distinct_customers` | `COUNT(DISTINCT f.customer_key)` | Integer (customers) | Unique customers represented |
| `gross_transaction_amount` | `SUM(f.amount)::NUMERIC(18, 2)` | Decimal (currency) | Total gross value transacted |
| `completed_gross_amount` | `COALESCE(SUM(amount) FILTER (WHERE status = 'COMPLETED'), 0.00)::NUMERIC(18, 2)` | Decimal (currency) | Completed gross value transacted |

---

### 2.4 Transaction Type Mix (`reporting.v_transaction_type_mix`)

- **Grain:** One row per `transaction_type_code`, `transaction_type_name`, `transaction_family`, and `currency`.
- **Source Layer:** `warehouse.fact_transactions` joined to `warehouse.dim_transaction_type`.

| Metric Name | SQL Formula / Definition | Output Units | Meaning |
|---|---|---|---|
| `total_transaction_count` | `COUNT(*)` | Integer (events) | Total events for transaction category |
| `completed_transaction_count` | `COUNT(*) FILTER (WHERE status = 'COMPLETED')` | Integer (events) | Settled events for category |
| `failed_transaction_count` | `COUNT(*) FILTER (WHERE status = 'FAILED')` | Integer (events) | Failed events for category |
| `pending_transaction_count` | `COUNT(*) FILTER (WHERE status = 'PENDING')` | Integer (events) | Pending events for category |
| `reversed_transaction_count` | `COUNT(*) FILTER (WHERE status = 'REVERSED')` | Integer (events) | Reversed events for category |
| `gross_transaction_amount` | `SUM(f.amount)::NUMERIC(18, 2)` | Decimal (currency) | Total gross value transacted |
| `completed_gross_amount` | `COALESCE(SUM(amount) FILTER (WHERE status = 'COMPLETED'), 0.00)::NUMERIC(18, 2)` | Decimal (currency) | Completed gross value transacted |

---

### 2.5 Data Quality Summary (`reporting.v_data_quality_summary`)

- **Grain:** One row per `rule_code`, `severity`, and `disposition`.
- **Source Layer:** `monitoring.data_quality_issues`.

| Metric Name | SQL Formula / Definition | Output Units | Meaning |
|---|---|---|---|
| `issue_count` | `COUNT(*)` | Integer (issue instances) | Total rule violations recorded |
| `affected_source_rows` | `COUNT(DISTINCT source_row_id)` | Integer (source rows) | Number of unique source staging rows impacted |
| `affected_batches` | `COUNT(DISTINCT batch_id)` | Integer (batches) | Number of ETL batches where this rule was triggered |

---

### 2.6 Pipeline Execution Health (`reporting.v_pipeline_execution_health`)

- **Grain:** One row per ETL batch run (`batch_id`).
- **Source Layer:** `monitoring.etl_batch_runs`.

| Metric Name | SQL Formula / Definition | Output Units | Meaning |
|---|---|---|---|
| `duration_seconds` | `ROUND(EXTRACT(EPOCH FROM (completed_at - started_at))::NUMERIC, 2)` | Decimal (seconds) | Total batch execution duration (`NULL` if in progress) |
| `status` | `b.status` | Enum string | `PENDING`, `RUNNING`, `SUCCEEDED`, `SUCCEEDED_WITH_REJECTIONS`, `FAILED` |
| `records_extracted` | `b.records_extracted` | Integer (rows) | Total rows read from source files |
| `records_staged` | `b.records_staged` | Integer (rows) | Total rows inserted into staging tables |
| `records_valid` | `b.records_valid` | Integer (rows) | Staged rows passing all validation contracts |
| `records_rejected` | `b.records_rejected` | Integer (rows) | Staged rows quarantined due to errors |
| `records_inserted` | `b.records_inserted` | Integer (rows) | New dimension/fact rows inserted into warehouse |
| `records_skipped` | `b.records_skipped` | Integer (rows) | Valid source events skipped as exact replays |
| `rejection_rate_pct` | `COALESCE(ROUND((records_rejected::NUMERIC / NULLIF(records_staged, 0)) * 100, 2), 0.00)` | Percentage (`0.00%` - `100.00%`) | Proportion of staged rows quarantined |
| `reconciliation_status` | `b.reconciliation_status` | Enum string | `RECONCILED` or `UNRECONCILED` |

---

### 2.7 Quarantine Inventory (`reporting.v_quarantine_inventory`)

- **Grain:** One row per `batch_id`, `entity_type`, and `primary_rule_code`.
- **Source Layer:** `quarantine.quarantined_records`.

| Metric Name | SQL Formula / Definition | Output Units | Meaning |
|---|---|---|---|
| `quarantined_rows` | `COUNT(*)` | Integer (rows) | Total entity rows quarantined |
| `recorded_issue_count` | `SUM(issue_count)` | Integer (issues) | Sum of validation issues recorded across quarantined rows |
| `first_quarantined_at` | `MIN(quarantined_at)` | TIMESTAMPTZ (UTC) | Earliest quarantine timestamp in batch grouping |
| `last_quarantined_at` | `MAX(quarantined_at)` | TIMESTAMPTZ (UTC) | Latest quarantine timestamp in batch grouping |

---

## 3. Query Execution & Performance Analysis

PostgreSQL execution plans were verified for all reporting views using `EXPLAIN`:
- **`reporting.v_daily_transaction_summary`**: Leverages `dim_date_pkey` for date dimension lookup, grouping by `date_key, currency`.
- **`reporting.v_deposit_withdrawal_analysis`**: Joins `dim_date` via PK scan and `dim_transaction_type` using cached index lookup (`dim_transaction_type_pkey`).
- **`reporting.v_branch_channel_activity`**: Joins `dim_branch` using PK index scan (`dim_branch_pkey`).
- **Filtering by Date or Currency**: When queries supply a `WHERE d.full_date BETWEEN ...` or `WHERE f.currency = ...`, PostgreSQL utilizes warehouse B-tree indexes `idx_fact_txns_date` and `idx_fact_txns_currency`.
- **Performance Guidelines**: Views avoid speculative indexes. Index usage is restricted to foreign keys, unique constraints, and high-cardinality status/currency filters already defined in `03_warehouse_schema.sql`.

---

## 4. Verification & Testing

Every metric defined in this document is verified by automated integration tests in [`tests/test_analytics_integration.py`](file:///c:/Gourav%20Sharma/work/BankFlow/tests/test_analytics_integration.py):
- Known-answer fixtures verify daily counts, status filtering, deposit vs. withdrawal amounts, branch/channel activity, and type mix.
- Data-quality tests verify that `issue_count` correctly counts multiple defects on single rows while `affected_source_rows` counts distinct rows.
- Zero-denominator tests verify that views executed on empty tables or zero-staged batches return `0.00` rather than throwing database division exceptions.
- Executed under PostgreSQL 17 in both local Docker Compose and GitHub Actions CI.
