"""
Live PostgreSQL integration tests for BankFlow Phase 2:
Validation Engine, Data Quality Issue Tracking, Quarantine Layer, and Batch Accounting.
"""

import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

from bankflow.__main__ import cli
from bankflow.config import DatabaseConfig, get_settings
from bankflow.constants import (
    BATCH_STATUS_FAILED,
    BATCH_STATUS_RUNNING,
    BATCH_STATUS_SUCCEEDED,
    BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS,
    CURRENCY_EUR,
    CURRENCY_USD,
    DISPOSITION_ACCEPTED,
    DISPOSITION_REJECTED,
    RULE_ACCOUNT_ID_DUPLICATE,
    RULE_ACCOUNT_ID_MISSING,
    RULE_ACCOUNT_NOT_FOUND,
    RULE_AMOUNT_MISSING,
    RULE_AMOUNT_PARSE_ERROR,
    RULE_AMOUNT_RULE_VIOLATION,
    RULE_BRANCH_ID_DUPLICATE,
    RULE_BRANCH_NAME_MISSING,
    RULE_BRANCH_REGION_MISSING,
    RULE_CHANNEL_UNSUPPORTED,
    RULE_CURRENCY_MISMATCH,
    RULE_CURRENCY_MISSING,
    RULE_CUSTOMER_ID_DUPLICATE,
    RULE_DATE_PARSE_ERROR,
    RULE_SOURCE_SYSTEM_MISSING,
    RULE_STATUS_UNSUPPORTED,
    RULE_TIMESTAMP_PARSE_ERROR,
    RULE_TXN_ID_DUPLICATE,
    RULE_TXN_ID_MISSING,
    RULE_TYPE_UNSUPPORTED,
)
from bankflow.db import check_connection, get_connection
from bankflow.generator.defects import DefectConfig
from bankflow.generator.generator import SyntheticDataGenerator
from bankflow.staging.loader import StagingLoader
from bankflow.staging.schema import init_staging_schema
from bankflow.validation import ValidationEngine, init_validation_schema
from click.testing import CliRunner


@pytest.fixture
def postgres_test_db():
    """Ensure dedicated test database is accessible and initialize base schemas."""
    test_db = get_settings().test_db
    success, err_msg = check_connection(test_db)
    if not success:
        if os.getenv("CI") or os.getenv("BANKFLOW_REQUIRE_INTEGRATION_TESTS"):
            pytest.fail(f"Required test database '{test_db.name}' is unreachable: {err_msg}")
        pytest.skip(f"Dedicated test database '{test_db.name}' is not accessible: {err_msg}")

    test_db.assert_safe_for_reset()

    with get_connection(test_db) as conn:
        init_staging_schema(conn)
        init_validation_schema(conn)

    return test_db


@pytest.mark.integration
def test_validation_schema_initialization(postgres_test_db):
    """Verify validation and quarantine tables and views exist and are repeatable."""
    with get_connection(postgres_test_db) as conn:
        # Run initialization twice to verify idempotency
        init_validation_schema(conn)
        init_validation_schema(conn)

        with conn.cursor() as cur:
            # Check monitoring.data_quality_issues
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'monitoring' AND table_name = 'data_quality_issues'
                ORDER BY ordinal_position;
            """)
            cols = {row[0]: row[1] for row in cur.fetchall()}
            assert "issue_id" in cols
            assert "batch_id" in cols
            assert "rule_code" in cols
            assert "severity" in cols
            assert "disposition" in cols

            # Check quarantine.quarantined_records
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'quarantine' AND table_name = 'quarantined_records'
                ORDER BY ordinal_position;
            """)
            q_cols = {row[0]: row[1] for row in cur.fetchall()}
            assert "quarantine_id" in q_cols
            assert "source_row_id" in q_cols
            assert "primary_rule_code" in q_cols

            # Check view quarantine.vw_quarantined_transactions
            cur.execute("""
                SELECT count(*) FROM quarantine.vw_quarantined_transactions;
            """)
            assert cur.fetchone()[0] >= 0


@pytest.mark.integration
def test_clean_dataset_validation(postgres_test_db, tmp_path: Path):
    """Verify that a 100% clean dataset validates cleanly with 0 rejections and 0 issues."""
    data_dir = tmp_path / "clean_data"
    generator = SyntheticDataGenerator(seed=101, defect_config=DefectConfig.clean())
    generator.export_all(data_dir, num_branches=3, num_customers=10, num_accounts=15, num_transactions=40)

    clean_batch_id = f"batch_clean_{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        stage_res = loader.ingest_dataset_directory(data_dir, batch_id=clean_batch_id)
        assert stage_res["status"] == BATCH_STATUS_SUCCEEDED

        engine = ValidationEngine(conn)
        summary = engine.validate_batch(clean_batch_id)

        # 3 branches + 10 customers + 15 accounts + 40 transactions = 68 records
        assert summary.batch_id == clean_batch_id
        assert summary.records_evaluated == 68
        assert summary.records_valid == 68
        assert summary.records_rejected == 0
        assert summary.total_issues_count == 0
        assert summary.batch_status == BATCH_STATUS_SUCCEEDED

        # Verify database metadata update
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, records_staged, records_valid, records_rejected
                FROM monitoring.etl_batch_runs
                WHERE batch_id = %s;
            """, (clean_batch_id,))
            run_row = cur.fetchone()
            assert run_row[0] == BATCH_STATUS_SUCCEEDED
            assert run_row[1] == 68
            assert run_row[2] == 68
            assert run_row[3] == 0

            # Verify 0 issues and 0 quarantined records
            cur.execute("SELECT count(*) FROM monitoring.data_quality_issues WHERE batch_id = %s;", (clean_batch_id,))
            assert cur.fetchone()[0] == 0

            cur.execute("SELECT count(*) FROM quarantine.quarantined_records WHERE batch_id = %s;", (clean_batch_id,))
            assert cur.fetchone()[0] == 0


@pytest.mark.integration
def test_defective_dataset_validation_and_quarantine(postgres_test_db, tmp_path: Path):
    """
    Verify that defective source records trigger exact stable rule codes,
    populate monitoring.data_quality_issues, quarantine invalid records traceable to staging,
    and preserve exact row/batch accounting.
    """
    data_dir = tmp_path / "defect_data"
    generator = SyntheticDataGenerator(seed=202, defect_config=DefectConfig.standard_test_defects())
    generator.export_all(data_dir, num_branches=3, num_customers=10, num_accounts=15, num_transactions=40)

    defect_batch_id = f"batch_defect_{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        stage_res = loader.ingest_dataset_directory(data_dir, batch_id=defect_batch_id)
        assert stage_res["status"] == BATCH_STATUS_SUCCEEDED

        engine = ValidationEngine(conn)
        summary = engine.validate_batch(defect_batch_id)

        assert summary.batch_id == defect_batch_id
        assert summary.records_evaluated == 68
        assert summary.records_rejected > 0
        assert summary.batch_status == BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS
        # Exact accounting invariant
        assert summary.records_evaluated == summary.records_valid + summary.records_rejected

        with conn.cursor() as cur:
            # Verify batch status in monitoring table
            cur.execute("""
                SELECT status, records_valid, records_rejected
                FROM monitoring.etl_batch_runs
                WHERE batch_id = %s;
            """, (defect_batch_id,))
            run_status, rec_valid, rec_rejected = cur.fetchone()
            assert run_status == BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS
            assert rec_valid == summary.records_valid
            assert rec_rejected == summary.records_rejected

            # Verify issues recorded in monitoring.data_quality_issues
            cur.execute("""
                SELECT DISTINCT rule_code
                FROM monitoring.data_quality_issues
                WHERE batch_id = %s;
            """, (defect_batch_id,))
            detected_rules = {r[0] for r in cur.fetchall()}

            expected_rules = {
                RULE_TXN_ID_MISSING,
                RULE_TXN_ID_DUPLICATE,
                RULE_ACCOUNT_ID_MISSING,
                RULE_ACCOUNT_NOT_FOUND,
                RULE_TYPE_UNSUPPORTED,
                RULE_CURRENCY_MISSING,
                RULE_TIMESTAMP_PARSE_ERROR,
                RULE_AMOUNT_MISSING,
                RULE_AMOUNT_PARSE_ERROR,
                RULE_AMOUNT_RULE_VIOLATION,
                RULE_STATUS_UNSUPPORTED,
                RULE_CHANNEL_UNSUPPORTED,
            }
            # All injected defect rules must be present
            assert expected_rules.issubset(detected_rules)

            # Verify quarantine records match summary.records_rejected
            cur.execute("""
                SELECT count(*)
                FROM quarantine.quarantined_records
                WHERE batch_id = %s;
            """, (defect_batch_id,))
            q_count = cur.fetchone()[0]
            assert q_count == summary.records_rejected

            # Verify traceability via quarantine view
            cur.execute("""
                SELECT quarantine_id, source_row_id, primary_rule_code, amount_raw, transaction_type, raw_payload
                FROM quarantine.vw_quarantined_transactions
                WHERE batch_id = %s;
            """, (defect_batch_id,))
            quarantined_txns = cur.fetchall()
            assert len(quarantined_txns) > 0
            for row in quarantined_txns:
                q_id, s_id, rule, amt, t_type, raw_payload = row
                assert q_id is not None
                assert s_id > 0
                assert rule in detected_rules
                # Ensure raw staging payload is preserved and accessible
                assert isinstance(raw_payload, dict)


@pytest.mark.integration
def test_validation_idempotency(postgres_test_db, tmp_path: Path):
    """
    Verify that executing validation repeatedly on the same batch does not
    duplicate issues or quarantine records.
    """
    data_dir = tmp_path / "idempotent_data"
    generator = SyntheticDataGenerator(seed=303, defect_config=DefectConfig.standard_test_defects())
    generator.export_all(data_dir, num_branches=3, num_customers=10, num_accounts=15, num_transactions=30)

    batch_id = f"batch_idem_{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        loader.ingest_dataset_directory(data_dir, batch_id=batch_id)

        engine = ValidationEngine(conn)

        # First run
        summary1 = engine.validate_batch(batch_id)

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM monitoring.data_quality_issues WHERE batch_id = %s;", (batch_id,))
            issues_run1 = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM quarantine.quarantined_records WHERE batch_id = %s;", (batch_id,))
            quarantine_run1 = cur.fetchone()[0]

        # Second run
        summary2 = engine.validate_batch(batch_id)

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM monitoring.data_quality_issues WHERE batch_id = %s;", (batch_id,))
            issues_run2 = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM quarantine.quarantined_records WHERE batch_id = %s;", (batch_id,))
            quarantine_run2 = cur.fetchone()[0]

        # Assert perfect idempotency: identical counts, no duplication
        assert summary1.records_valid == summary2.records_valid
        assert summary1.records_rejected == summary2.records_rejected
        assert summary1.total_issues_count == summary2.total_issues_count
        assert issues_run1 == issues_run2
        assert quarantine_run1 == quarantine_run2


@pytest.mark.integration
def test_cli_validate_command(postgres_test_db, tmp_path: Path):
    """Verify CLI `bankflow validate <batch_id> --test-db` command."""
    data_dir = tmp_path / "cli_validate_data"
    generator = SyntheticDataGenerator(seed=404, defect_config=DefectConfig.clean())
    generator.export_all(data_dir, num_branches=2, num_customers=5, num_accounts=5, num_transactions=20)

    batch_id = f"batch_cli_{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        loader.ingest_dataset_directory(data_dir, batch_id=batch_id)

    runner = CliRunner()
    result = runner.invoke(cli, ["validate", batch_id, "--test-db"])
    assert result.exit_code == 0
    assert "[SUCCEEDED] Validation completed for batch" in result.output
    assert batch_id in result.output
    assert "Records evaluated:" in result.output
    assert "Records valid:     32" in result.output


@pytest.mark.integration
def test_validation_lifecycle_guard_rejects_failed_batch(postgres_test_db):
    """
    Verify that validate_batch refuses staging batches marked FAILED or RUNNING,
    and preserves original status, error_summary, records_staged, records_valid,
    records_rejected, and leaves validated_at unchanged.
    """
    batch_failed_id = f"batch_failed_{uuid.uuid4().hex[:8]}"
    batch_running_id = f"batch_running_{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            # 1. Insert FAILED staging batch
            cur.execute("""
                INSERT INTO monitoring.etl_batch_runs (
                    batch_id, source_name, status, records_staged, records_valid, records_rejected,
                    error_summary, started_at, completed_at
                ) VALUES (
                    %s, 'test_source', %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                );
            """, (
                batch_failed_id,
                BATCH_STATUS_FAILED,
                15,
                0,
                0,
                "Staging failed: malformed CSV encoding in branches.csv",
            ))

            # 2. Insert RUNNING staging batch
            cur.execute("""
                INSERT INTO monitoring.etl_batch_runs (
                    batch_id, source_name, status, records_staged, records_valid, records_rejected,
                    error_summary, started_at
                ) VALUES (
                    %s, 'test_source', %s, %s, %s, %s, %s, CURRENT_TIMESTAMP
                );
            """, (
                batch_running_id,
                BATCH_STATUS_RUNNING,
                10,
                0,
                0,
                None,
            ))

        engine = ValidationEngine(conn)

        # Expect FAILED batch rejection
        with pytest.raises(ValueError, match="cannot be validated"):
            engine.validate_batch(batch_failed_id)

        # Expect RUNNING batch rejection
        with pytest.raises(ValueError, match="cannot be validated"):
            engine.validate_batch(batch_running_id)

        # Verify nothing was mutated in monitoring.etl_batch_runs for the FAILED batch
        with conn.cursor() as cur:
            cur.execute("""
                SELECT status, error_summary, records_staged, records_valid, records_rejected, validated_at
                FROM monitoring.etl_batch_runs
                WHERE batch_id = %s;
            """, (batch_failed_id,))
            row = cur.fetchone()
            assert row[0] == BATCH_STATUS_FAILED
            assert row[1] == "Staging failed: malformed CSV encoding in branches.csv"
            assert row[2] == 15
            assert row[3] == 0
            assert row[4] == 0
            assert row[5] is None


@pytest.mark.integration
def test_cross_batch_reference_resolution_restrictions(postgres_test_db):
    """
    Verify that cross-batch reference lookups require batches with a completed
    and successful validation outcome, excluding unvalidated or failed batches.
    """
    b_prev_val = f"batch_prev_val_{uuid.uuid4().hex[:8]}"
    b_prev_unval = f"batch_prev_unval_{uuid.uuid4().hex[:8]}"
    b_prev_fail = f"batch_prev_fail_{uuid.uuid4().hex[:8]}"
    b_cur_txns = f"batch_cur_txns_{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            # 1. Previously validated successful batch
            cur.execute("""
                INSERT INTO monitoring.etl_batch_runs (
                    batch_id, source_name, status, records_staged, records_valid, records_rejected,
                    started_at, completed_at, validated_at
                ) VALUES (
                    %s, 'test_source', %s, 3, 3, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                );
            """, (b_prev_val, BATCH_STATUS_SUCCEEDED))

            cur.execute("""
                INSERT INTO staging.stg_branches (
                    batch_id, source_file, source_row_number, branch_id, branch_name, region, raw_payload
                ) VALUES (%s, 'branches.csv', 1, 'BR-PREV', 'Downtown', 'NORTH', '{}');
            """, (b_prev_val,))
            cur.execute("""
                INSERT INTO staging.stg_customers (
                    batch_id, source_file, source_row_number, customer_id, customer_segment, created_date_raw, customer_status, raw_payload
                ) VALUES (%s, 'customers.csv', 1, 'CUST-PREV', 'RETAIL', '2026-01-01', 'ACTIVE', '{}');
            """, (b_prev_val,))
            cur.execute("""
                INSERT INTO staging.stg_accounts (
                    batch_id, source_file, source_row_number, account_id, customer_id, branch_id, account_type, account_status, opened_date_raw, currency, raw_payload
                ) VALUES (%s, 'accounts.csv', 1, 'ACC-PREV-VALID', 'CUST-PREV', 'BR-PREV', 'CHECKING', 'OPEN', '2026-01-01', 'USD', '{}');
            """, (b_prev_val,))

            # 2. Staged but unvalidated batch
            cur.execute("""
                INSERT INTO monitoring.etl_batch_runs (
                    batch_id, source_name, status, records_staged, records_valid, records_rejected,
                    started_at, completed_at, validated_at
                ) VALUES (
                    %s, 'test_source', %s, 1, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL
                );
            """, (b_prev_unval, BATCH_STATUS_SUCCEEDED))
            cur.execute("""
                INSERT INTO staging.stg_accounts (
                    batch_id, source_file, source_row_number, account_id, customer_id, branch_id, account_type, account_status, opened_date_raw, currency, raw_payload
                ) VALUES (%s, 'accounts.csv', 1, 'ACC-UNVALIDATED', 'CUST-PREV', 'BR-PREV', 'CHECKING', 'OPEN', '2026-01-01', 'USD', '{}');
            """, (b_prev_unval,))

            # 3. Failed staging batch
            cur.execute("""
                INSERT INTO monitoring.etl_batch_runs (
                    batch_id, source_name, status, records_staged, records_valid, records_rejected,
                    error_summary, started_at, completed_at, validated_at
                ) VALUES (
                    %s, 'test_source', %s, 1, 0, 0, 'Staging failed', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, NULL
                );
            """, (b_prev_fail, BATCH_STATUS_FAILED))
            cur.execute("""
                INSERT INTO staging.stg_accounts (
                    batch_id, source_file, source_row_number, account_id, customer_id, branch_id, account_type, account_status, opened_date_raw, currency, raw_payload
                ) VALUES (%s, 'accounts.csv', 1, 'ACC-FAILED', 'CUST-PREV', 'BR-PREV', 'CHECKING', 'OPEN', '2026-01-01', 'USD', '{}');
            """, (b_prev_fail,))

            # 4. Current transaction batch referencing the above three accounts
            cur.execute("""
                INSERT INTO monitoring.etl_batch_runs (
                    batch_id, source_name, status, records_staged, records_valid, records_rejected,
                    started_at, completed_at
                ) VALUES (
                    %s, 'test_source', %s, 3, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                );
            """, (b_cur_txns, BATCH_STATUS_SUCCEEDED))

            cur.execute("""
                INSERT INTO staging.stg_transactions (
                    batch_id, source_file, source_row_number, transaction_id, account_id,
                    transaction_type, amount_raw, currency, transaction_timestamp_raw,
                    status, channel, counterparty_account_id, source_system, raw_payload
                ) VALUES
                    (%s, 'txns.csv', 1, 'TXN-OK', 'ACC-PREV-VALID', 'DEPOSIT', '100.00', 'USD', '2026-03-01T12:00:00+00:00', 'COMPLETED', 'ONLINE', NULL, 'CORE', '{}'),
                    (%s, 'txns.csv', 2, 'TXN-UNVAL', 'ACC-UNVALIDATED', 'DEPOSIT', '100.00', 'USD', '2026-03-01T12:00:00+00:00', 'COMPLETED', 'ONLINE', NULL, 'CORE', '{}'),
                    (%s, 'txns.csv', 3, 'TXN-FAIL', 'ACC-FAILED', 'DEPOSIT', '100.00', 'USD', '2026-03-01T12:00:00+00:00', 'COMPLETED', 'ONLINE', NULL, 'CORE', '{}');
            """, (b_cur_txns, b_cur_txns, b_cur_txns))

        engine = ValidationEngine(conn)
        summary = engine.validate_batch(b_cur_txns)

        assert summary.records_evaluated == 3
        assert summary.records_valid == 1
        assert summary.records_rejected == 2
        assert summary.batch_status == BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS

        with conn.cursor() as cur:
            cur.execute("""
                SELECT source_row_id, primary_rule_code, account_id
                FROM quarantine.vw_quarantined_transactions
                WHERE batch_id = %s
                ORDER BY source_row_number;
            """, (b_cur_txns,))
            quarantined = cur.fetchall()
            assert len(quarantined) == 2
            # Both unvalidated and failed-batch account references must be rejected with RULE_ACCOUNT_NOT_FOUND
            assert quarantined[0][1] == RULE_ACCOUNT_NOT_FOUND
            assert quarantined[0][2] == "ACC-UNVALIDATED"
            assert quarantined[1][1] == RULE_ACCOUNT_NOT_FOUND
            assert quarantined[1][2] == "ACC-FAILED"


@pytest.mark.integration
def test_duplicate_entities_and_currency_mismatch_integration(postgres_test_db):
    """
    Verify:
    1. Duplicate branch, customer, and account IDs are rejected under stable duplicate rules.
    2. Duplicated accounts do not enter the trusted account-reference set, causing transactions
       that reference them to be rejected.
    3. Currency consistency: transactions whose currency mismatches account currency are rejected.
    """
    batch_id = f"batch_dup_curr_{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO monitoring.etl_batch_runs (
                    batch_id, source_name, status, records_staged, records_valid, records_rejected,
                    started_at, completed_at
                ) VALUES (
                    %s, 'test_source', %s, 12, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                );
            """, (batch_id, BATCH_STATUS_SUCCEEDED))

            # 3 branches: 1 clean, 2 duplicates
            cur.execute("""
                INSERT INTO staging.stg_branches (
                    batch_id, source_file, source_row_number, branch_id, branch_name, region, raw_payload
                ) VALUES
                    (%s, 'branches.csv', 1, 'BR-VALID', 'Valid Branch', 'NORTH', '{}'),
                    (%s, 'branches.csv', 2, 'BR-DUP', 'Duplicate Branch A', 'EAST', '{}'),
                    (%s, 'branches.csv', 3, 'BR-DUP', 'Duplicate Branch B', 'WEST', '{}');
            """, (batch_id, batch_id, batch_id))

            # 3 customers: 1 clean, 2 duplicates
            cur.execute("""
                INSERT INTO staging.stg_customers (
                    batch_id, source_file, source_row_number, customer_id, customer_segment, created_date_raw, customer_status, raw_payload
                ) VALUES
                    (%s, 'customers.csv', 1, 'CUST-VALID', 'RETAIL', '2026-01-01', 'ACTIVE', '{}'),
                    (%s, 'customers.csv', 2, 'CUST-DUP', 'RETAIL', '2026-01-01', 'ACTIVE', '{}'),
                    (%s, 'customers.csv', 3, 'CUST-DUP', 'RETAIL', '2026-01-01', 'ACTIVE', '{}');
            """, (batch_id, batch_id, batch_id))

            # 3 accounts: 1 clean USD account, 2 duplicates
            cur.execute("""
                INSERT INTO staging.stg_accounts (
                    batch_id, source_file, source_row_number, account_id, customer_id, branch_id, account_type, account_status, opened_date_raw, currency, raw_payload
                ) VALUES
                    (%s, 'accounts.csv', 1, 'ACC-VALID-USD', 'CUST-VALID', 'BR-VALID', 'CHECKING', 'OPEN', '2026-01-01', 'USD', '{}'),
                    (%s, 'accounts.csv', 2, 'ACC-DUP', 'CUST-VALID', 'BR-VALID', 'CHECKING', 'OPEN', '2026-01-01', 'USD', '{}'),
                    (%s, 'accounts.csv', 3, 'ACC-DUP', 'CUST-VALID', 'BR-VALID', 'CHECKING', 'OPEN', '2026-01-01', 'USD', '{}');
            """, (batch_id, batch_id, batch_id))

            # 3 transactions:
            # 1: Clean USD transaction on ACC-VALID-USD -> ACCEPTED
            # 2: EUR transaction on ACC-VALID-USD -> REJECTED with RULE_CURRENCY_MISMATCH
            # 3: Transaction referencing ACC-DUP -> REJECTED with RULE_ACCOUNT_NOT_FOUND
            cur.execute("""
                INSERT INTO staging.stg_transactions (
                    batch_id, source_file, source_row_number, transaction_id, account_id,
                    transaction_type, amount_raw, currency, transaction_timestamp_raw,
                    status, channel, counterparty_account_id, source_system, raw_payload
                ) VALUES
                    (%s, 'txns.csv', 1, 'TXN-OK', 'ACC-VALID-USD', 'DEPOSIT', '100.00', 'USD', '2026-03-01T12:00:00+00:00', 'COMPLETED', 'ONLINE', NULL, 'CORE', '{}'),
                    (%s, 'txns.csv', 2, 'TXN-MISMATCH', 'ACC-VALID-USD', 'DEPOSIT', '100.00', 'EUR', '2026-03-01T12:00:00+00:00', 'COMPLETED', 'ONLINE', NULL, 'CORE', '{}'),
                    (%s, 'txns.csv', 3, 'TXN-DUP-REF', 'ACC-DUP', 'DEPOSIT', '100.00', 'USD', '2026-03-01T12:00:00+00:00', 'COMPLETED', 'ONLINE', NULL, 'CORE', '{}');
            """, (batch_id, batch_id, batch_id))

        engine = ValidationEngine(conn)
        summary = engine.validate_batch(batch_id)

        # 3 branches + 3 customers + 3 accounts + 3 txns = 12 records
        assert summary.records_evaluated == 12
        # Clean: 1 branch, 1 customer, 1 account, 1 txn = 4 valid
        assert summary.records_valid == 4
        # Rejected: 2 branches, 2 customers, 2 accounts, 2 txns = 8 rejected
        assert summary.records_rejected == 8
        assert summary.batch_status == BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS

        with conn.cursor() as cur:
            # Check distinct rule codes
            cur.execute("""
                SELECT DISTINCT rule_code
                FROM monitoring.data_quality_issues
                WHERE batch_id = %s;
            """, (batch_id,))
            issues = {r[0] for r in cur.fetchall()}
            assert RULE_BRANCH_ID_DUPLICATE in issues
            assert RULE_CUSTOMER_ID_DUPLICATE in issues
            assert RULE_ACCOUNT_ID_DUPLICATE in issues
            assert RULE_CURRENCY_MISMATCH in issues
            assert RULE_ACCOUNT_NOT_FOUND in issues

            # Verify quarantine count
            cur.execute("SELECT count(*) FROM quarantine.quarantined_records WHERE batch_id = %s;", (batch_id,))
            assert cur.fetchone()[0] == 8
