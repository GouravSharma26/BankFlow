"""
PostgreSQL integration tests for schema initialization, staging ingestion, and batch tracking.
Runs against the dedicated test database when configured and reachable.
"""

from pathlib import Path

import psycopg2
import pytest

from bankflow.config import DatabaseConfig, get_settings
from bankflow.constants import BATCH_STATUS_SUCCEEDED
from bankflow.db import check_connection, get_connection
from bankflow.staging.loader import StagingLoader
from bankflow.staging.schema import init_staging_schema


def is_test_db_available(config: DatabaseConfig) -> bool:
    """Check if test database can be connected to."""
    success, _ = check_connection(config)
    return success


@pytest.mark.integration
def test_postgres_schema_init_and_staging_ingestion(clean_dataset_dir: Path, defective_dataset_dir: Path):
    test_db = get_settings().test_db

    if not is_test_db_available(test_db):
        pytest.skip(
            f"Dedicated test database '{test_db.name}' on {test_db.host}:{test_db.port} is not accessible. "
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
