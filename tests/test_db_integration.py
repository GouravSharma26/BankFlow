"""
PostgreSQL integration tests for schema initialization, staging ingestion, and batch tracking.
Runs against the dedicated test database when configured and reachable.
"""

import os
from pathlib import Path
from typing import Tuple

import psycopg2
import pytest

from bankflow.config import DatabaseConfig, get_settings
from bankflow.constants import (
    BATCH_STATUS_FAILED,
    BATCH_STATUS_SUCCEEDED,
    RULE_FILE_EMPTY,
    RULE_FILE_REQUIRED_COLUMN_MISSING,
)
from bankflow.db import check_connection, get_connection
from bankflow.staging.loader import StagingLoader
from bankflow.staging.schema import init_staging_schema


def check_test_db_accessible(config: DatabaseConfig) -> Tuple[bool, str]:
    """Check if test database can be connected to and return (success, message)."""
    return check_connection(config)


@pytest.mark.integration
def test_postgres_schema_init_and_staging_ingestion(clean_dataset_dir: Path, defective_dataset_dir: Path):
    test_db = get_settings().test_db

    success, err_msg = check_test_db_accessible(test_db)
    if not success:
        if os.getenv("CI") or os.getenv("BANKFLOW_REQUIRE_INTEGRATION_TESTS"):
            pytest.fail(f"Required test database '{test_db.name}' is unreachable: {err_msg}")
        pytest.skip(
            f"Dedicated test database '{test_db.name}' on {test_db.host}:{test_db.port} is not accessible: {err_msg}. "
            "Configure local credentials in .env to run PostgreSQL integration tests."
        )

    # Enforce safety guardrail: must be a test database
    test_db.assert_safe_for_reset()

    with get_connection(test_db) as conn:
        # 1. Initialize schema
        init_staging_schema(conn)

        # 2. Ingest clean dataset
        loader = StagingLoader(conn)
        result = loader.ingest_dataset_directory(clean_dataset_dir)

        assert result["status"] == BATCH_STATUS_SUCCEEDED
        batch_id = result["batch_id"]
        assert result["records_extracted"] == result["records_staged"]
        assert result["records_staged"] > 0

        # 3. Verify batch record in monitoring table
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, records_extracted, records_staged
                FROM monitoring.etl_batch_runs
                WHERE batch_id = %s;
            """, (batch_id,))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == BATCH_STATUS_SUCCEEDED
            assert row[1] == result["records_extracted"]
            assert row[2] == result["records_staged"]

            # 4. Verify transaction staging rows and lineage
            cur.execute("""
                SELECT source_file, source_row_number, raw_payload, ingested_at
                FROM staging.stg_transactions
                WHERE batch_id = %s
                LIMIT 5;
            """, (batch_id,))
            txn_rows = cur.fetchall()
            assert len(txn_rows) > 0
            for r in txn_rows:
                assert r[0] == "transactions.csv"
                assert r[1] >= 1  # 1-based row number
                assert r[2] is not None  # JSON raw payload
                assert r[3] is not None  # Ingestion timestamp

        # 5. Ingest defective dataset: verifies malformed text amounts/timestamps are preserved
        defective_result = loader.ingest_dataset_directory(defective_dataset_dir)
        assert defective_result["status"] == BATCH_STATUS_SUCCEEDED
        def_batch_id = defective_result["batch_id"]

        with conn.cursor() as cur:
            # Check that raw non-numeric amount was staged rather than discarded
            cur.execute("""
                SELECT amount_raw, transaction_timestamp_raw
                FROM staging.stg_transactions
                WHERE batch_id = %s AND amount_raw = 'TEN_DOLLARS';
            """, (def_batch_id,))
            bad_amt_row = cur.fetchone()
            assert bad_amt_row is not None
            assert bad_amt_row[0] == "TEN_DOLLARS"


@pytest.mark.integration
def test_staging_with_explicit_batch_id(clean_dataset_dir: Path):
    """Verify that providing an explicit batch_id registers and updates the batch run correctly."""
    test_db = get_settings().test_db
    success, err_msg = check_test_db_accessible(test_db)
    if not success:
        if os.getenv("CI") or os.getenv("BANKFLOW_REQUIRE_INTEGRATION_TESTS"):
            pytest.fail(f"Required test database '{test_db.name}' is unreachable: {err_msg}")
        pytest.skip(f"Dedicated test database '{test_db.name}' is not accessible: {err_msg}")

    test_db.assert_safe_for_reset()
    custom_batch_id = "test_custom_batch_2026_01"

    with get_connection(test_db) as conn:
        init_staging_schema(conn)
        loader = StagingLoader(conn)
        result = loader.ingest_dataset_directory(clean_dataset_dir, batch_id=custom_batch_id)

        assert result["batch_id"] == custom_batch_id
        assert result["status"] == BATCH_STATUS_SUCCEEDED

        with conn.cursor() as cur:
            cur.execute("""
                SELECT batch_id, status, records_extracted, records_staged
                FROM monitoring.etl_batch_runs
                WHERE batch_id = %s;
            """, (custom_batch_id,))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == custom_batch_id
            assert row[1] == BATCH_STATUS_SUCCEEDED
            assert row[2] == result["records_extracted"]
            assert row[3] == result["records_staged"]


@pytest.mark.integration
def test_staging_failed_batch_accounting(tmp_path: Path):
    """Verify that a batch with a file violation records FAILED status, error summary, and counts."""
    test_db = get_settings().test_db
    success, err_msg = check_test_db_accessible(test_db)
    if not success:
        if os.getenv("CI") or os.getenv("BANKFLOW_REQUIRE_INTEGRATION_TESTS"):
            pytest.fail(f"Required test database '{test_db.name}' is unreachable: {err_msg}")
        pytest.skip(f"Dedicated test database '{test_db.name}' is not accessible: {err_msg}")

    test_db.assert_safe_for_reset()
    bad_dir = tmp_path / "corrupt_dataset"
    bad_dir.mkdir(parents=True, exist_ok=True)

    # Valid branches
    (bad_dir / "branches.csv").write_text("branch_id,branch_name,region\nBR-01,Test,NORTH\n", encoding="utf-8")
    # Empty customers file (violates non-empty dataset contract)
    (bad_dir / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\n", encoding="utf-8")
    # Valid accounts
    (bad_dir / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-01,C-01,BR-01,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
    # Valid transactions
    (bad_dir / "transactions.csv").write_text("transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\nTX-01,ACC-01,DEPOSIT,100.00,USD,2026-01-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n", encoding="utf-8")

    fail_batch_id = "test_fail_batch_accounting"
    with get_connection(test_db) as conn:
        init_staging_schema(conn)
        loader = StagingLoader(conn)
        result = loader.ingest_dataset_directory(bad_dir, batch_id=fail_batch_id)

        assert result["status"] == BATCH_STATUS_FAILED
        assert result["error_code"] == RULE_FILE_EMPTY

        # Query batch run to verify persisted accounting
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, records_extracted, records_staged, error_summary
                FROM monitoring.etl_batch_runs
                WHERE batch_id = %s;
            """, (fail_batch_id,))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == BATCH_STATUS_FAILED
            # branches was extracted and staged (1 record) before customers failed
            assert row[1] == 1  # records_extracted
            assert row[2] == 1  # records_staged
            assert RULE_FILE_EMPTY in row[3]
