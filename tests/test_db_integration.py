"""
PostgreSQL integration tests for schema initialization, staging ingestion, and batch tracking.
Runs against the dedicated test database when configured and reachable.
"""

import os
import uuid
from pathlib import Path
from typing import Tuple

import psycopg2
import pytest

from bankflow.config import DatabaseConfig, get_settings
from bankflow.constants import (
    BATCH_STATUS_FAILED,
    BATCH_STATUS_SUCCEEDED,
    RULE_BATCH_ALREADY_EXISTS,
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
    custom_batch_id = f"test_custom_{uuid.uuid4().hex[:8]}"

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

    fail_batch_id = f"test_fail_{uuid.uuid4().hex[:8]}"
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


@pytest.mark.integration
def test_batch_id_collision_preserves_original_state(clean_dataset_dir: Path):
    """
    Verify that attempting to reuse an existing batch_id is rejected without
    modifying the original batch record or duplicating staged rows, and produces
    a useful error for the CLI caller.
    """
    from click.testing import CliRunner
    from bankflow.__main__ import cli

    test_db = get_settings().test_db
    success, err_msg = check_test_db_accessible(test_db)
    if not success:
        if os.getenv("CI") or os.getenv("BANKFLOW_REQUIRE_INTEGRATION_TESTS"):
            pytest.fail(f"Required test database '{test_db.name}' is unreachable: {err_msg}")
        pytest.skip(f"Dedicated test database '{test_db.name}' is not accessible: {err_msg}")

    test_db.assert_safe_for_reset()
    collision_batch_id = f"test_collision_{uuid.uuid4().hex[:8]}"

    with get_connection(test_db) as conn:
        init_staging_schema(conn)
        loader = StagingLoader(conn)

        # 1. Initial ingestion succeeds
        first_result = loader.ingest_dataset_directory(clean_dataset_dir, batch_id=collision_batch_id)
        assert first_result["status"] == BATCH_STATUS_SUCCEEDED
        original_extracted = first_result["records_extracted"]
        original_staged = first_result["records_staged"]

        # 2. Attempt second ingestion with the identical batch_id
        second_result = loader.ingest_dataset_directory(clean_dataset_dir, batch_id=collision_batch_id)
        assert second_result["status"] == BATCH_STATUS_FAILED
        assert second_result["error_code"] == RULE_BATCH_ALREADY_EXISTS
        assert "already exists" in second_result["error_message"]

        # 3. Verify original batch run record in monitoring table is intact and NOT mutated to FAILED
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, records_extracted, records_staged, error_summary
                FROM monitoring.etl_batch_runs
                WHERE batch_id = %s;
            """, (collision_batch_id,))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == BATCH_STATUS_SUCCEEDED  # Crucial: NOT overwritten or corrupted
            assert row[1] == original_extracted
            assert row[2] == original_staged
            assert row[3] is None  # No error summary on original successful run

            # 4. Verify staged rows count in staging.stg_transactions is unchanged (no duplicate insertions)
            cur.execute("""
                SELECT count(*)
                FROM staging.stg_transactions
                WHERE batch_id = %s;
            """, (collision_batch_id,))
            txn_count = cur.fetchone()[0]
            assert txn_count == 50

    # 5. Verify CLI caller receives a useful error and exit code 1
    runner = CliRunner()
    cli_res = runner.invoke(
        cli,
        [
            "stage",
            "--input-dir", str(clean_dataset_dir),
            "--batch-id", collision_batch_id,
            "--test-db",
        ],
    )
    assert cli_res.exit_code != 0
    assert "BATCH_ALREADY_EXISTS" in cli_res.output
    assert f"Batch with ID '{collision_batch_id}' already exists" in cli_res.output


@pytest.mark.integration
def test_raw_staging_preservation_and_surplus_fields(tmp_path: Path):
    """
    Verify that raw staging preserves source field values without trimming whitespace
    and preserves surplus CSV fields in raw_payload under '_surplus'.
    Tests:
    - A transaction ID with surrounding whitespace (e.g. '  TXN-SPACE-99  ')
    - An amount with surrounding whitespace (e.g. '  450.75  ')
    - A row with more values than the declared header (surplus values)
    - Assertions that the source representation is preserved and no values disappear silently.
    """
    test_db = get_settings().test_db
    success, err_msg = check_test_db_accessible(test_db)
    if not success:
        if os.getenv("CI") or os.getenv("BANKFLOW_REQUIRE_INTEGRATION_TESTS"):
            pytest.fail(f"Required test database '{test_db.name}' is unreachable: {err_msg}")
        pytest.skip(f"Dedicated test database '{test_db.name}' is not accessible: {err_msg}")

    test_db.assert_safe_for_reset()
    dataset_dir = tmp_path / "raw_preservation_dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    # Valid branches with whitespace
    (dataset_dir / "branches.csv").write_text(
        "branch_id,branch_name,region\n"
        "  BR-SPACE-01  ,  Downtown Branch  ,  NORTH  \n",
        encoding="utf-8",
    )
    # Valid customers with whitespace
    (dataset_dir / "customers.csv").write_text(
        "customer_id,customer_segment,created_date,customer_status\n"
        "  CUST-SPACE-01  ,  RETAIL  ,  2026-01-01  ,  ACTIVE  \n",
        encoding="utf-8",
    )
    # Valid accounts with whitespace
    (dataset_dir / "accounts.csv").write_text(
        "account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\n"
        "  ACC-SPACE-01  ,  CUST-SPACE-01  ,  BR-SPACE-01  ,CHECKING,OPEN,2026-01-01,USD\n",
        encoding="utf-8",
    )
    # Transactions with:
    # Row 1: transaction_id with surrounding whitespace and amount with surrounding whitespace
    # Row 2: surplus fields (more values than header)
    # Row 3: combined whitespace and surplus fields
    (dataset_dir / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "  TXN-SPACE-99  ,ACC-01,DEPOSIT,  450.75  ,USD,2026-01-01T00:00:00+00:00,COMPLETED,ONLINE,,CORE\n"
        "TXN-SURPLUS-100,ACC-01,WITHDRAWAL,50.00,USD,2026-01-01T01:00:00+00:00,COMPLETED,ATM,,CORE,SURPLUS_VAL_ALPHA,SURPLUS_VAL_BETA\n"
        "  TXN-BOTH-101  ,ACC-01,TRANSFER,  1000.00  ,USD,2026-01-01T02:00:00+00:00,COMPLETED,BRANCH,,CORE,  SURPLUS_WITH_SPACES  \n",
        encoding="utf-8",
    )

    batch_id = f"test_raw_preserve_{uuid.uuid4().hex[:8]}"

    with get_connection(test_db) as conn:
        init_staging_schema(conn)
        loader = StagingLoader(conn)
        result = loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id)

        assert result["status"] == BATCH_STATUS_SUCCEEDED
        assert result["records_staged"] == 6  # 1 branch + 1 customer + 1 account + 3 transactions = 6

        with conn.cursor() as cur:
            # Check branches: preserved whitespace in staging columns and raw_payload
            cur.execute("""
                SELECT branch_id, branch_name, region, raw_payload
                FROM staging.stg_branches
                WHERE batch_id = %s;
            """, (batch_id,))
            br_row = cur.fetchone()
            assert br_row is not None
            assert br_row[0] == "  BR-SPACE-01  "
            assert br_row[1] == "  Downtown Branch  "
            assert br_row[2] == "  NORTH  "
            assert br_row[3]["branch_id"] == "  BR-SPACE-01  "

            # Check customers: preserved whitespace
            cur.execute("""
                SELECT customer_id, customer_segment, created_date_raw, raw_payload
                FROM staging.stg_customers
                WHERE batch_id = %s;
            """, (batch_id,))
            cust_row = cur.fetchone()
            assert cust_row is not None
            assert cust_row[0] == "  CUST-SPACE-01  "
            assert cust_row[1] == "  RETAIL  "
            assert cust_row[2] == "  2026-01-01  "
            assert cust_row[3]["customer_id"] == "  CUST-SPACE-01  "

            # Check transactions:
            cur.execute("""
                SELECT source_row_number, transaction_id, amount_raw, raw_payload
                FROM staging.stg_transactions
                WHERE batch_id = %s
                ORDER BY source_row_number;
            """, (batch_id,))
            tx_rows = cur.fetchall()
            assert len(tx_rows) == 3

            # Row 1: whitespace preserved without trimming
            r1_num, r1_txid, r1_amt, r1_payload = tx_rows[0]
            assert r1_num == 1
            assert r1_txid == "  TXN-SPACE-99  "
            assert r1_amt == "  450.75  "
            assert r1_payload["transaction_id"] == "  TXN-SPACE-99  "
            assert r1_payload["amount"] == "  450.75  "
            assert "_surplus" not in r1_payload

            # Row 2: surplus values preserved under _surplus
            r2_num, r2_txid, r2_amt, r2_payload = tx_rows[1]
            assert r2_num == 2
            assert r2_txid == "TXN-SURPLUS-100"
            assert r2_amt == "50.00"
            assert r2_payload["transaction_id"] == "TXN-SURPLUS-100"
            assert r2_payload["_surplus"] == ["SURPLUS_VAL_ALPHA", "SURPLUS_VAL_BETA"]

            # Row 3: combined whitespace and surplus preserved
            r3_num, r3_txid, r3_amt, r3_payload = tx_rows[2]
            assert r3_num == 3
            assert r3_txid == "  TXN-BOTH-101  "
            assert r3_amt == "  1000.00  "
            assert r3_payload["transaction_id"] == "  TXN-BOTH-101  "
            assert r3_payload["amount"] == "  1000.00  "
            assert r3_payload["_surplus"] == ["  SURPLUS_WITH_SPACES  "]
