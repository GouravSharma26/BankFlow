-- BankFlow Phase 2: Validation & Quarantine Schema
-- Creates data quality issue tracking and quarantine tables

CREATE SCHEMA IF NOT EXISTS monitoring;
CREATE SCHEMA IF NOT EXISTS quarantine;

-- Add explicit validation timestamp to monitoring.etl_batch_runs
ALTER TABLE monitoring.etl_batch_runs ADD COLUMN IF NOT EXISTS validated_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_batch_validated ON monitoring.etl_batch_runs (validated_at);

-- 1. Data Quality Issues Table
CREATE TABLE IF NOT EXISTS monitoring.data_quality_issues (
    issue_id VARCHAR(64) PRIMARY KEY,
    batch_id VARCHAR(64) NOT NULL REFERENCES monitoring.etl_batch_runs(batch_id) ON DELETE CASCADE,
    entity_type VARCHAR(32) NOT NULL,
    source_row_id BIGINT,
    source_row_number INT NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    rule_code VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL,
    reason TEXT NOT NULL,
    disposition VARCHAR(32) NOT NULL,
    detected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dqi_batch ON monitoring.data_quality_issues (batch_id);
CREATE INDEX IF NOT EXISTS idx_dqi_rule ON monitoring.data_quality_issues (rule_code);
CREATE INDEX IF NOT EXISTS idx_dqi_severity ON monitoring.data_quality_issues (severity);
CREATE INDEX IF NOT EXISTS idx_dqi_row ON monitoring.data_quality_issues (source_row_id);

-- 2. Quarantine Records Table (relational reference to staging rows)
CREATE TABLE IF NOT EXISTS quarantine.quarantined_records (
    quarantine_id VARCHAR(64) PRIMARY KEY,
    batch_id VARCHAR(64) NOT NULL REFERENCES monitoring.etl_batch_runs(batch_id) ON DELETE CASCADE,
    entity_type VARCHAR(32) NOT NULL,
    source_row_id BIGINT NOT NULL,
    source_row_number INT NOT NULL,
    source_file VARCHAR(255) NOT NULL,
    primary_rule_code VARCHAR(64) NOT NULL,
    issue_count INT NOT NULL DEFAULT 1,
    quarantined_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quarantine_batch ON quarantine.quarantined_records (batch_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_row ON quarantine.quarantined_records (source_row_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_rule ON quarantine.quarantined_records (primary_rule_code);

-- 3. Quarantined Transactions View (joins quarantine with staging without raw-data duplication)
CREATE OR REPLACE VIEW quarantine.vw_quarantined_transactions AS
SELECT
    q.quarantine_id,
    q.batch_id,
    q.source_row_id,
    q.source_row_number,
    q.source_file,
    q.primary_rule_code,
    q.issue_count,
    q.quarantined_at,
    st.transaction_id,
    st.account_id,
    st.transaction_type,
    st.amount_raw,
    st.currency,
    st.transaction_timestamp_raw,
    st.status,
    st.channel,
    st.counterparty_account_id,
    st.source_system,
    st.raw_payload
FROM quarantine.quarantined_records q
JOIN staging.stg_transactions st ON q.source_row_id = st.source_row_id
WHERE q.entity_type = 'TRANSACTION';
