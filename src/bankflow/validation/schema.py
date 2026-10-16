"""
Validation and quarantine schema initialization.
Executes idempotent DDL creating monitoring.data_quality_issues and quarantine.quarantined_records tables.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from psycopg2.extensions import connection as PgConnection

from bankflow.config import DatabaseConfig
from bankflow.db import get_connection, transaction

SQL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "sql"
VALIDATION_SQL_FILE = SQL_DIR / "02_validation_quarantine_schema.sql"

# Fallback embedded DDL in case external SQL file is missing
VALIDATION_DDL = """
CREATE SCHEMA IF NOT EXISTS monitoring;
CREATE SCHEMA IF NOT EXISTS quarantine;

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
"""


def init_validation_schema(
    conn: Optional[PgConnection] = None,
    config: Optional[DatabaseConfig] = None,
) -> None:
    """
    Initialize validation and quarantine tables idempotently.
    Can be passed an open connection or a DatabaseConfig.
    """
    ddl_to_run = VALIDATION_DDL
    if VALIDATION_SQL_FILE.exists():
        try:
            ddl_to_run = VALIDATION_SQL_FILE.read_text(encoding="utf-8")
        except Exception:
            ddl_to_run = VALIDATION_DDL

    if conn is not None:
        with transaction(conn):
            with conn.cursor() as cur:
                cur.execute(ddl_to_run)
    elif config is not None:
        with get_connection(config) as new_conn:
            with transaction(new_conn):
                with new_conn.cursor() as cur:
                    cur.execute(ddl_to_run)
    else:
        raise ValueError("Either an open psycopg2 connection or a DatabaseConfig must be provided.")
