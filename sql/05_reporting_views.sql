-- BankFlow Phase 4: Reporting Schema and Conformed Analytical Views
-- Creates schema `reporting` and analytical views providing reusable, tested metrics.
-- All monetary amounts represent positive gross event values, grouped by currency.

CREATE SCHEMA IF NOT EXISTS reporting;

-- 1. Daily Transaction Summary
-- Grain: 1 row per reporting date and currency.
-- Includes both total and completed event counts, active accounts, and gross amounts.
CREATE OR REPLACE VIEW reporting.v_daily_transaction_summary AS
SELECT
    d.date_key,
    d.full_date AS reporting_date,
    d.year_number,
    d.month_number,
    d.month_name,
    d.day_name,
    d.is_weekend,
    f.currency,
    COUNT(*) AS total_transaction_count,
    COUNT(*) FILTER (WHERE f.status = 'COMPLETED') AS completed_transaction_count,
    COUNT(*) FILTER (WHERE f.status = 'PENDING') AS pending_transaction_count,
    COUNT(*) FILTER (WHERE f.status = 'FAILED') AS failed_transaction_count,
    COUNT(*) FILTER (WHERE f.status = 'REVERSED') AS reversed_transaction_count,
    COUNT(DISTINCT f.account_key) AS active_accounts,
    COUNT(DISTINCT f.customer_key) AS active_customers,
    SUM(f.amount)::NUMERIC(18, 2) AS gross_transaction_amount,
    COALESCE(SUM(f.amount) FILTER (WHERE f.status = 'COMPLETED'), 0.00)::NUMERIC(18, 2) AS completed_gross_amount
FROM warehouse.fact_transactions AS f
JOIN warehouse.dim_date AS d ON d.date_key = f.date_key
GROUP BY
    d.date_key, d.full_date, d.year_number, d.month_number,
    d.month_name, d.day_name, d.is_weekend, f.currency;

-- 2. Deposit versus Withdrawal Analysis
-- Grain: 1 row per reporting date and currency.
-- Compares deposit and withdrawal event volumes and gross amounts under explicit status rules.
-- Reversals are adjustments and are reported separately; they do not decrement gross flow.
CREATE OR REPLACE VIEW reporting.v_deposit_withdrawal_analysis AS
SELECT
    d.date_key,
    d.full_date AS reporting_date,
    f.currency,
    -- Deposits
    COUNT(*) FILTER (WHERE t.transaction_type_code = 'DEPOSIT') AS deposit_count,
    COALESCE(SUM(f.amount) FILTER (WHERE t.transaction_type_code = 'DEPOSIT'), 0.00)::NUMERIC(18, 2) AS deposit_gross_amount,
    COUNT(*) FILTER (WHERE t.transaction_type_code = 'DEPOSIT' AND f.status = 'COMPLETED') AS completed_deposit_count,
    COALESCE(SUM(f.amount) FILTER (WHERE t.transaction_type_code = 'DEPOSIT' AND f.status = 'COMPLETED'), 0.00)::NUMERIC(18, 2) AS completed_deposit_gross_amount,
    -- Withdrawals
    COUNT(*) FILTER (WHERE t.transaction_type_code = 'WITHDRAWAL') AS withdrawal_count,
    COALESCE(SUM(f.amount) FILTER (WHERE t.transaction_type_code = 'WITHDRAWAL'), 0.00)::NUMERIC(18, 2) AS withdrawal_gross_amount,
    COUNT(*) FILTER (WHERE t.transaction_type_code = 'WITHDRAWAL' AND f.status = 'COMPLETED') AS completed_withdrawal_count,
    COALESCE(SUM(f.amount) FILTER (WHERE t.transaction_type_code = 'WITHDRAWAL' AND f.status = 'COMPLETED'), 0.00)::NUMERIC(18, 2) AS completed_withdrawal_gross_amount,
    -- Reversals / Adjustments (distinct event category, tracked explicitly)
    COUNT(*) FILTER (WHERE t.transaction_type_code = 'REVERSAL') AS reversal_count,
    COALESCE(SUM(f.amount) FILTER (WHERE t.transaction_type_code = 'REVERSAL'), 0.00)::NUMERIC(18, 2) AS reversal_gross_amount
FROM warehouse.fact_transactions AS f
JOIN warehouse.dim_date AS d ON d.date_key = f.date_key
JOIN warehouse.dim_transaction_type AS t ON t.type_key = f.type_key
GROUP BY d.date_key, d.full_date, f.currency;

-- 3. Branch and Channel Activity
-- Grain: 1 row per region, branch, channel, and currency.
-- Exposes regional distribution, operational facility, and transaction initiation channel.
CREATE OR REPLACE VIEW reporting.v_branch_channel_activity AS
SELECT
    b.region,
    b.branch_id,
    b.branch_name,
    f.channel,
    f.currency,
    COUNT(*) AS total_transaction_count,
    COUNT(*) FILTER (WHERE f.status = 'COMPLETED') AS completed_transaction_count,
    COUNT(DISTINCT f.account_key) AS distinct_accounts,
    COUNT(DISTINCT f.customer_key) AS distinct_customers,
    SUM(f.amount)::NUMERIC(18, 2) AS gross_transaction_amount,
    COALESCE(SUM(f.amount) FILTER (WHERE f.status = 'COMPLETED'), 0.00)::NUMERIC(18, 2) AS completed_gross_amount
FROM warehouse.fact_transactions AS f
JOIN warehouse.dim_branch AS b ON b.branch_key = f.branch_key
GROUP BY b.region, b.branch_id, b.branch_name, f.channel, f.currency;

-- 4. Transaction Type Mix
-- Grain: 1 row per transaction type code and currency.
-- Categorizes events by business code, display label, and accounting family.
CREATE OR REPLACE VIEW reporting.v_transaction_type_mix AS
SELECT
    t.transaction_type_code,
    t.transaction_type_name,
    t.transaction_family,
    f.currency,
    COUNT(*) AS total_transaction_count,
    COUNT(*) FILTER (WHERE f.status = 'COMPLETED') AS completed_transaction_count,
    COUNT(*) FILTER (WHERE f.status = 'FAILED') AS failed_transaction_count,
    COUNT(*) FILTER (WHERE f.status = 'PENDING') AS pending_transaction_count,
    COUNT(*) FILTER (WHERE f.status = 'REVERSED') AS reversed_transaction_count,
    SUM(f.amount)::NUMERIC(18, 2) AS gross_transaction_amount,
    COALESCE(SUM(f.amount) FILTER (WHERE f.status = 'COMPLETED'), 0.00)::NUMERIC(18, 2) AS completed_gross_amount
FROM warehouse.fact_transactions AS f
JOIN warehouse.dim_transaction_type AS t ON t.type_key = f.type_key
GROUP BY t.transaction_type_code, t.transaction_type_name, t.transaction_family, f.currency;

-- 5. Data Quality Summary
-- Grain: 1 row per rule code, severity, and disposition.
-- Separates individual quality issue records from distinct affected source rows and batches.
CREATE OR REPLACE VIEW reporting.v_data_quality_summary AS
SELECT
    i.rule_code,
    i.severity,
    i.disposition,
    COUNT(*) AS issue_count,
    COUNT(DISTINCT i.source_row_id) AS affected_source_rows,
    COUNT(DISTINCT i.batch_id) AS affected_batches
FROM monitoring.data_quality_issues AS i
GROUP BY i.rule_code, i.severity, i.disposition;

-- 6. Pipeline Execution Health
-- Grain: 1 row per ETL batch run.
-- Tracks batch lifecycle, row accounting, execution duration, and reconciliation outcome.
CREATE OR REPLACE VIEW reporting.v_pipeline_execution_health AS
SELECT
    b.batch_id,
    b.source_name,
    b.started_at,
    b.completed_at,
    CASE
        WHEN b.completed_at IS NOT NULL AND b.started_at IS NOT NULL
        THEN ROUND(EXTRACT(EPOCH FROM (b.completed_at - b.started_at))::NUMERIC, 2)
        ELSE NULL
    END AS duration_seconds,
    b.status,
    b.records_extracted,
    b.records_staged,
    b.records_valid,
    b.records_rejected,
    b.records_inserted,
    b.records_updated,
    b.records_skipped,
    COALESCE(
        ROUND((b.records_rejected::NUMERIC / NULLIF(b.records_staged, 0)) * 100, 2),
        0.00
    ) AS rejection_rate_pct,
    b.reconciliation_status,
    b.error_summary
FROM monitoring.etl_batch_runs AS b;

-- 7. Quarantine Inventory
-- Grain: 1 row per batch, entity type, and primary rule code.
-- Inspects rows quarantined during validation with counts and recorded issue totals.
CREATE OR REPLACE VIEW reporting.v_quarantine_inventory AS
SELECT
    q.batch_id,
    q.entity_type,
    q.primary_rule_code,
    COUNT(*) AS quarantined_rows,
    SUM(q.issue_count) AS recorded_issue_count,
    MIN(q.quarantined_at) AS first_quarantined_at,
    MAX(q.quarantined_at) AS last_quarantined_at
FROM quarantine.quarantined_records AS q
GROUP BY q.batch_id, q.entity_type, q.primary_rule_code;

-- 8. Transaction Details
-- Grain: 1 row per accepted transaction event in the warehouse.
-- Narrowly scoped conformed view for transaction search, filtering, and detail displays.
CREATE OR REPLACE VIEW reporting.v_transaction_details AS
SELECT
    f.transaction_id,
    f.source_system,
    da.account_id,
    dc.customer_id,
    db.branch_id,
    db.branch_name,
    db.region,
    t.transaction_type_code AS transaction_type,
    t.transaction_type_name AS type_name,
    t.transaction_family,
    f.amount,
    f.currency,
    f.status,
    f.channel,
    f.transaction_timestamp,
    d.full_date AS reporting_date,
    f.source_batch_id AS batch_id,
    f.loaded_at
FROM warehouse.fact_transactions AS f
JOIN warehouse.dim_date AS d ON d.date_key = f.date_key
JOIN warehouse.dim_transaction_type AS t ON t.type_key = f.type_key
JOIN warehouse.dim_account AS da ON da.account_key = f.account_key
JOIN warehouse.dim_customer AS dc ON dc.customer_key = f.customer_key
JOIN warehouse.dim_branch AS db ON db.branch_key = f.branch_key;
