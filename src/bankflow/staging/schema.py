"""
Staging and monitoring schema initialization.
Executes idempotent DDL creating monitoring and staging tables.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from psycopg2.extensions import connection as PgConnection

from bankflow.config import DatabaseConfig
from bankflow.db import get_connection, transaction

SQL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "sql"
STAGING_SQL_FILE = SQL_DIR / "01_staging_schema.sql"

# Fallback embedded DDL in case external SQL file is missing
STAGING_DDL = """
CREATE SCHEMA IF NOT EXISTS monitoring;
CREATE SCHEMA IF NOT EXISTS staging;

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

CREATE INDEX IF NOT EXISTS idx_batch_status_started
    ON monitoring.etl_batch_runs (status, started_at DESC);

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
"""


def init_staging_schema(conn: PgConnection) -> None:
    """Execute staging schema creation statements within a transaction."""
    ddl = STAGING_DDL
    if STAGING_SQL_FILE.exists():
        try:
            ddl = STAGING_SQL_FILE.read_text(encoding="utf-8")
        except Exception:
            pass

    with transaction(conn):
        with conn.cursor() as cur:
            cur.execute(ddl)


def initialize_database(config: Optional[DatabaseConfig] = None) -> None:
    """Convenience helper to initialize database using given or default config."""
    with get_connection(config) as conn:
        init_staging_schema(conn)
