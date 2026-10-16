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
    BATCH_STATUS_SUCCEEDED,
    BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS,
    DISPOSITION_ACCEPTED,
    DISPOSITION_REJECTED,
    RULE_ACCOUNT_ID_MISSING,
    RULE_ACCOUNT_NOT_FOUND,
    RULE_AMOUNT_MISSING,
    RULE_AMOUNT_PARSE_ERROR,
    RULE_AMOUNT_RULE_VIOLATION,
    RULE_CHANNEL_UNSUPPORTED,
    RULE_CURRENCY_MISSING,
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
