-- BankFlow Phase 4: Analytics Query Pack
-- Run from the repository root against a database initialized by `bankflow init-db`.
-- All source data is synthetic. Amount summaries are gross amounts, grouped by currency.
-- These queries do not infer debit/credit sign or perform arbitrary FX conversion.
-- UTC timestamp semantics are preserved for all date-based metrics.

-- 1. Daily transaction activity by reporting date and currency.
SELECT
    d.full_date AS reporting_date,
    d.day_name,
    d.is_weekend,
    f.currency,
    COUNT(*) AS total_transaction_count,
    COUNT(*) FILTER (WHERE f.status = 'COMPLETED') AS completed_transaction_count,
    COUNT(DISTINCT f.account_key) AS active_accounts,
    COUNT(DISTINCT f.customer_key) AS active_customers,
    SUM(f.amount)::NUMERIC(18, 2) AS gross_transaction_amount,
    COALESCE(SUM(f.amount) FILTER (WHERE f.status = 'COMPLETED'), 0.00)::NUMERIC(18, 2) AS completed_gross_amount
FROM warehouse.fact_transactions AS f
JOIN warehouse.dim_date AS d ON d.date_key = f.date_key
GROUP BY d.full_date, d.day_name, d.is_weekend, f.currency
ORDER BY d.full_date DESC, f.currency;

-- 2. Deposit-versus-withdrawal analysis with explicit status and reversal semantics.
-- Reversals are tracked as adjustments and do not decrement gross transaction amounts.
SELECT
    d.full_date AS reporting_date,
    f.currency,
    -- Deposit metrics
    COUNT(*) FILTER (WHERE t.transaction_type_code = 'DEPOSIT') AS deposit_count,
    COALESCE(SUM(f.amount) FILTER (WHERE t.transaction_type_code = 'DEPOSIT'), 0.00)::NUMERIC(18, 2) AS deposit_gross_amount,
    COUNT(*) FILTER (WHERE t.transaction_type_code = 'DEPOSIT' AND f.status = 'COMPLETED') AS completed_deposit_count,
    COALESCE(SUM(f.amount) FILTER (WHERE t.transaction_type_code = 'DEPOSIT' AND f.status = 'COMPLETED'), 0.00)::NUMERIC(18, 2) AS completed_deposit_gross_amount,
    -- Withdrawal metrics
    COUNT(*) FILTER (WHERE t.transaction_type_code = 'WITHDRAWAL') AS withdrawal_count,
    COALESCE(SUM(f.amount) FILTER (WHERE t.transaction_type_code = 'WITHDRAWAL'), 0.00)::NUMERIC(18, 2) AS withdrawal_gross_amount,
    COUNT(*) FILTER (WHERE t.transaction_type_code = 'WITHDRAWAL' AND f.status = 'COMPLETED') AS completed_withdrawal_count,
    COALESCE(SUM(f.amount) FILTER (WHERE t.transaction_type_code = 'WITHDRAWAL' AND f.status = 'COMPLETED'), 0.00)::NUMERIC(18, 2) AS completed_withdrawal_gross_amount,
    -- Reversal / adjustment metrics (distinct event category)
    COUNT(*) FILTER (WHERE t.transaction_type_code = 'REVERSAL') AS reversal_count,
    COALESCE(SUM(f.amount) FILTER (WHERE t.transaction_type_code = 'REVERSAL'), 0.00)::NUMERIC(18, 2) AS reversal_gross_amount
FROM warehouse.fact_transactions AS f
JOIN warehouse.dim_date AS d ON d.date_key = f.date_key
JOIN warehouse.dim_transaction_type AS t ON t.type_key = f.type_key
GROUP BY d.full_date, f.currency
ORDER BY d.full_date DESC, f.currency;

-- 3. Transaction activity by branch, region, channel, and currency.
SELECT
    b.region,
    b.branch_id,
    b.branch_name,
    f.channel,
    f.currency,
    COUNT(*) AS total_transaction_count,
    COUNT(*) FILTER (WHERE f.status = 'COMPLETED') AS completed_transaction_count,
    COUNT(DISTINCT f.customer_key) AS distinct_customers,
    COUNT(DISTINCT f.account_key) AS distinct_accounts,
    SUM(f.amount)::NUMERIC(18, 2) AS gross_transaction_amount,
    COALESCE(SUM(f.amount) FILTER (WHERE f.status = 'COMPLETED'), 0.00)::NUMERIC(18, 2) AS completed_gross_amount
FROM warehouse.fact_transactions AS f
JOIN warehouse.dim_branch AS b ON b.branch_key = f.branch_key
GROUP BY b.region, b.branch_id, b.branch_name, f.channel, f.currency
ORDER BY total_transaction_count DESC, b.region, b.branch_name, f.channel, f.currency;

-- 4. Transaction-type mix by event count and gross event value.
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
GROUP BY t.transaction_type_code, t.transaction_type_name, t.transaction_family, f.currency
ORDER BY total_transaction_count DESC, t.transaction_type_code, f.currency;

-- 5. Data-quality summaries separating individual issue records from affected source rows and batches.
SELECT
    i.rule_code,
    i.severity,
    i.disposition,
    COUNT(*) AS issue_count,
    COUNT(DISTINCT i.source_row_id) AS affected_source_rows,
    COUNT(DISTINCT i.batch_id) AS affected_batches
FROM monitoring.data_quality_issues AS i
GROUP BY i.rule_code, i.severity, i.disposition
ORDER BY issue_count DESC, i.rule_code, i.severity, i.disposition;

-- 6. ETL batch health, showing source-to-warehouse accounting, duration, and reconciliation status.
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
FROM monitoring.etl_batch_runs AS b
ORDER BY b.started_at DESC
LIMIT 25;

-- 7. Quarantine volume by entity, primary rule code, and batch.
SELECT
    q.batch_id,
    q.entity_type,
    q.primary_rule_code,
    COUNT(*) AS quarantined_rows,
    SUM(q.issue_count) AS recorded_issue_count,
    MIN(q.quarantined_at) AS first_quarantined_at,
    MAX(q.quarantined_at) AS last_quarantined_at
FROM quarantine.quarantined_records AS q
GROUP BY q.batch_id, q.entity_type, q.primary_rule_code
ORDER BY quarantined_rows DESC, q.batch_id, q.entity_type, q.primary_rule_code;
