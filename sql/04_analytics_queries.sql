-- BankFlow analytics query pack
-- Run from the repository root against a database initialized by `bankflow init-db`.
-- All source data must be synthetic. Amount summaries are gross amounts, grouped by
-- currency; these queries do not infer debit/credit sign or perform FX conversion.

-- 1. Monthly transaction volume and gross amount by currency.
SELECT
    d.year_number,
    d.month_number,
    d.month_name,
    f.currency,
    COUNT(*) AS transaction_count,
    COUNT(DISTINCT f.account_key) AS active_accounts,
    SUM(f.amount)::NUMERIC(18, 2) AS gross_transaction_amount
FROM warehouse.fact_transactions AS f
JOIN warehouse.dim_date AS d ON d.date_key = f.date_key
GROUP BY d.year_number, d.month_number, d.month_name, f.currency
ORDER BY d.year_number, d.month_number, f.currency;

-- 2. Transaction mix by type, family, channel, and currency.
SELECT
    t.transaction_type_code,
    t.transaction_type_name,
    t.transaction_family,
    f.channel,
    f.currency,
    COUNT(*) AS transaction_count,
    SUM(f.amount)::NUMERIC(18, 2) AS gross_transaction_amount
FROM warehouse.fact_transactions AS f
JOIN warehouse.dim_transaction_type AS t ON t.type_key = f.type_key
GROUP BY
    t.transaction_type_code, t.transaction_type_name, t.transaction_family,
    f.channel, f.currency
ORDER BY transaction_count DESC, t.transaction_type_code, f.channel, f.currency;

-- 3. Branch/region activity. Results are split by currency to avoid mixed-currency sums.
SELECT
    b.region,
    b.branch_id,
    b.branch_name,
    f.currency,
    COUNT(*) AS transaction_count,
    COUNT(DISTINCT f.customer_key) AS distinct_customers,
    COUNT(DISTINCT f.account_key) AS distinct_accounts,
    SUM(f.amount)::NUMERIC(18, 2) AS gross_transaction_amount
FROM warehouse.fact_transactions AS f
JOIN warehouse.dim_branch AS b ON b.branch_key = f.branch_key
GROUP BY b.region, b.branch_id, b.branch_name, f.currency
ORDER BY transaction_count DESC, b.region, b.branch_name, f.currency;

-- 4. Data-quality issue summary by rule, severity, and disposition.
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

-- 5. Recent batch health, showing source-to-warehouse accounting and reconciliation status.
SELECT
    b.batch_id,
    b.source_name,
    b.started_at,
    b.completed_at,
    b.status,
    b.records_extracted,
    b.records_staged,
    b.records_valid,
    b.records_rejected,
    b.records_inserted,
    b.records_skipped,
    b.reconciliation_status,
    b.error_summary
FROM monitoring.etl_batch_runs AS b
ORDER BY b.started_at DESC
LIMIT 25;

-- 6. Quarantine volume by entity and primary data-quality rule.
SELECT
    q.entity_type,
    q.primary_rule_code,
    COUNT(*) AS quarantined_rows,
    SUM(q.issue_count) AS recorded_issue_count,
    COUNT(DISTINCT q.batch_id) AS affected_batches
FROM quarantine.quarantined_records AS q
GROUP BY q.entity_type, q.primary_rule_code
ORDER BY quarantined_rows DESC, q.entity_type, q.primary_rule_code;
