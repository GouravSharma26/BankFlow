-- BankFlow Phase 3: Dimensional Warehouse Schema
-- Creates dimensional model: dim_date, dim_transaction_type, dim_branch, dim_customer, dim_account, fact_transactions

-- 1. Create Warehouse Schema
CREATE SCHEMA IF NOT EXISTS warehouse;

-- 2. Date Dimension (Pre-populated calendar dimension)
CREATE TABLE IF NOT EXISTS warehouse.dim_date (
    date_key INT PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    day_of_month INT NOT NULL,
    day_of_week INT NOT NULL,
    day_name VARCHAR(16) NOT NULL,
    week_of_year INT NOT NULL,
    month_number INT NOT NULL,
    month_name VARCHAR(16) NOT NULL,
    quarter_number INT NOT NULL,
    year_number INT NOT NULL,
    is_weekend BOOLEAN NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dim_date_full_date ON warehouse.dim_date (full_date);

-- Populate Date Dimension (2020 through 2035)
INSERT INTO warehouse.dim_date (
    date_key, full_date, day_of_month, day_of_week, day_name,
    week_of_year, month_number, month_name, quarter_number, year_number, is_weekend
)
SELECT
    TO_CHAR(d, 'YYYYMMDD')::INT AS date_key,
    d::DATE AS full_date,
    EXTRACT(DAY FROM d)::INT AS day_of_month,
    EXTRACT(ISODOW FROM d)::INT AS day_of_week,
    TRIM(TO_CHAR(d, 'Day')) AS day_name,
    EXTRACT(WEEK FROM d)::INT AS week_of_year,
    EXTRACT(MONTH FROM d)::INT AS month_number,
    TRIM(TO_CHAR(d, 'Month')) AS month_name,
    EXTRACT(QUARTER FROM d)::INT AS quarter_number,
    EXTRACT(YEAR FROM d)::INT AS year_number,
    (EXTRACT(ISODOW FROM d) IN (6, 7)) AS is_weekend
FROM generate_series('2020-01-01'::DATE, '2035-12-31'::DATE, '1 day'::INTERVAL) d
ON CONFLICT (date_key) DO NOTHING;

-- 3. Transaction Type Dimension
CREATE TABLE IF NOT EXISTS warehouse.dim_transaction_type (
    type_key SERIAL PRIMARY KEY,
    transaction_type_code VARCHAR(32) NOT NULL UNIQUE,
    transaction_type_name VARCHAR(64) NOT NULL,
    transaction_family VARCHAR(32) NOT NULL
);

-- Seed Transaction Type Dimension
INSERT INTO warehouse.dim_transaction_type (transaction_type_code, transaction_type_name, transaction_family)
VALUES
    ('DEPOSIT', 'Deposit', 'CREDIT'),
    ('WITHDRAWAL', 'Withdrawal', 'DEBIT'),
    ('TRANSFER', 'Transfer', 'TRANSFER'),
    ('PAYMENT', 'Payment', 'DEBIT'),
    ('FEE', 'Fee', 'DEBIT'),
    ('REVERSAL', 'Reversal', 'ADJUSTMENT')
ON CONFLICT (transaction_type_code) DO NOTHING;

-- 4. Branch Dimension
CREATE TABLE IF NOT EXISTS warehouse.dim_branch (
    branch_key SERIAL PRIMARY KEY,
    branch_id VARCHAR(64) NOT NULL UNIQUE,
    branch_name VARCHAR(128) NOT NULL,
    region VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_branch_region ON warehouse.dim_branch (region);

-- 5. Customer Dimension
CREATE TABLE IF NOT EXISTS warehouse.dim_customer (
    customer_key SERIAL PRIMARY KEY,
    customer_id VARCHAR(64) NOT NULL UNIQUE,
    customer_segment VARCHAR(32) NOT NULL,
    customer_status VARCHAR(32) NOT NULL,
    created_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_customer_segment ON warehouse.dim_customer (customer_segment);
CREATE INDEX IF NOT EXISTS idx_dim_customer_status ON warehouse.dim_customer (customer_status);

-- 6. Account Dimension
CREATE TABLE IF NOT EXISTS warehouse.dim_account (
    account_key SERIAL PRIMARY KEY,
    account_id VARCHAR(64) NOT NULL UNIQUE,
    customer_key INT NOT NULL REFERENCES warehouse.dim_customer(customer_key),
    branch_key INT NOT NULL REFERENCES warehouse.dim_branch(branch_key),
    account_type VARCHAR(32) NOT NULL,
    account_status VARCHAR(32) NOT NULL,
    currency VARCHAR(10) NOT NULL,
    opened_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_account_customer ON warehouse.dim_account (customer_key);
CREATE INDEX IF NOT EXISTS idx_dim_account_branch ON warehouse.dim_account (branch_key);
CREATE INDEX IF NOT EXISTS idx_dim_account_currency ON warehouse.dim_account (currency);

-- 7. Fact Transactions Table (Grain: 1 row per accepted transaction event)
CREATE TABLE IF NOT EXISTS warehouse.fact_transactions (
    transaction_key BIGSERIAL PRIMARY KEY,
    transaction_id VARCHAR(64) NOT NULL,
    source_system VARCHAR(64) NOT NULL,
    account_key INT NOT NULL REFERENCES warehouse.dim_account(account_key),
    customer_key INT NOT NULL REFERENCES warehouse.dim_customer(customer_key),
    branch_key INT NOT NULL REFERENCES warehouse.dim_branch(branch_key),
    date_key INT NOT NULL REFERENCES warehouse.dim_date(date_key),
    type_key INT NOT NULL REFERENCES warehouse.dim_transaction_type(type_key),
    amount NUMERIC(18, 2) NOT NULL CHECK (amount > 0.00),
    currency VARCHAR(10) NOT NULL,
    status VARCHAR(32) NOT NULL,
    channel VARCHAR(32) NOT NULL,
    transaction_timestamp TIMESTAMPTZ NOT NULL,
    source_batch_id VARCHAR(64) NOT NULL REFERENCES monitoring.etl_batch_runs(batch_id),
    source_row_id BIGINT NOT NULL,
    loaded_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fact_transactions_source_event UNIQUE (source_system, transaction_id)
);

CREATE INDEX IF NOT EXISTS idx_fact_txns_account ON warehouse.fact_transactions (account_key);
CREATE INDEX IF NOT EXISTS idx_fact_txns_customer ON warehouse.fact_transactions (customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_txns_branch ON warehouse.fact_transactions (branch_key);
CREATE INDEX IF NOT EXISTS idx_fact_txns_date ON warehouse.fact_transactions (date_key);
CREATE INDEX IF NOT EXISTS idx_fact_txns_type ON warehouse.fact_transactions (type_key);
CREATE INDEX IF NOT EXISTS idx_fact_txns_batch ON warehouse.fact_transactions (source_batch_id);
CREATE INDEX IF NOT EXISTS idx_fact_txns_status ON warehouse.fact_transactions (status);
CREATE INDEX IF NOT EXISTS idx_fact_txns_currency ON warehouse.fact_transactions (currency);
