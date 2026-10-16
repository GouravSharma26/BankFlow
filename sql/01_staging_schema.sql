-- BankFlow Phase 1: Staging and Monitoring Schemas
-- Creates operational metadata and raw staging tables

-- 1. Create Schemas
CREATE SCHEMA IF NOT EXISTS monitoring;
CREATE SCHEMA IF NOT EXISTS staging;

-- 2. Monitoring: Batch Lifecycle and Run Metadata
CREATE TABLE IF NOT EXISTS monitoring.etl_batch_runs (
    batch_id VARCHAR(64) PRIMARY KEY,
    source_name VARCHAR(255) NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL,
    records_extracted INT DEFAULT 0,
    records_staged INT DEFAULT 0,
    records_valid INT DEFAULT 0,
    records_rejected INT DEFAULT 0,
    records_inserted INT DEFAULT 0,
    records_updated INT DEFAULT 0,
    records_skipped INT DEFAULT 0,
    reconciliation_status VARCHAR(32),
    error_summary TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Index for querying batches by status and start time
CREATE INDEX IF NOT EXISTS idx_batch_status_started
    ON monitoring.etl_batch_runs (status, started_at DESC);

-- 3. Staging: Raw Branches
CREATE TABLE IF NOT EXISTS staging.stg_branches (
    source_row_id BIGSERIAL PRIMARY KEY,
    branch_id VARCHAR(64),
    branch_name VARCHAR(128),
    region VARCHAR(64),
    source_file VARCHAR(255) NOT NULL,
    batch_id VARCHAR(64) NOT NULL REFERENCES monitoring.etl_batch_runs(batch_id) ON DELETE CASCADE,
    source_row_number INT NOT NULL,
    raw_payload JSONB,
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stg_branches_batch
    ON staging.stg_branches (batch_id);

-- 4. Staging: Raw Customers
CREATE TABLE IF NOT EXISTS staging.stg_customers (
    source_row_id BIGSERIAL PRIMARY KEY,
    customer_id VARCHAR(64),
    customer_segment VARCHAR(32),
    created_date_raw VARCHAR(64),
    customer_status VARCHAR(32),
    source_file VARCHAR(255) NOT NULL,
    batch_id VARCHAR(64) NOT NULL REFERENCES monitoring.etl_batch_runs(batch_id) ON DELETE CASCADE,
    source_row_number INT NOT NULL,
    raw_payload JSONB,
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stg_customers_batch
    ON staging.stg_customers (batch_id);

-- 5. Staging: Raw Accounts
CREATE TABLE IF NOT EXISTS staging.stg_accounts (
    source_row_id BIGSERIAL PRIMARY KEY,
    account_id VARCHAR(64),
    customer_id VARCHAR(64),
    branch_id VARCHAR(64),
    account_type VARCHAR(32),
    account_status VARCHAR(32),
    opened_date_raw VARCHAR(64),
    currency VARCHAR(10),
    source_file VARCHAR(255) NOT NULL,
    batch_id VARCHAR(64) NOT NULL REFERENCES monitoring.etl_batch_runs(batch_id) ON DELETE CASCADE,
    source_row_number INT NOT NULL,
    raw_payload JSONB,
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stg_accounts_batch
    ON staging.stg_accounts (batch_id);

-- 6. Staging: Raw Transactions
CREATE TABLE IF NOT EXISTS staging.stg_transactions (
    source_row_id BIGSERIAL PRIMARY KEY,
    transaction_id VARCHAR(64),
    account_id VARCHAR(64),
    transaction_type VARCHAR(32),
    amount_raw VARCHAR(64),
    currency VARCHAR(10),
    transaction_timestamp_raw VARCHAR(64),
    status VARCHAR(32),
    channel VARCHAR(32),
    counterparty_account_id VARCHAR(64),
    source_system VARCHAR(64),
    source_file VARCHAR(255) NOT NULL,
    batch_id VARCHAR(64) NOT NULL REFERENCES monitoring.etl_batch_runs(batch_id) ON DELETE CASCADE,
    source_row_number INT NOT NULL,
    raw_payload JSONB,
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_stg_transactions_batch
    ON staging.stg_transactions (batch_id);

CREATE INDEX IF NOT EXISTS idx_stg_transactions_txn_id
    ON staging.stg_transactions (transaction_id);
