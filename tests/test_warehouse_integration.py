"""
Live PostgreSQL integration tests for BankFlow Phase 3:
Warehouse Schema, Dimensional Loading, Database Idempotency, and Reconciliation.
"""

import os
import uuid
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from bankflow.__main__ import cli
from bankflow.config import get_settings
from bankflow.constants import (
    BATCH_STATUS_FAILED,
    BATCH_STATUS_PENDING,
    BATCH_STATUS_RUNNING,
    BATCH_STATUS_SUCCEEDED,
    BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS,
    DISPOSITION_SKIPPED,
    RULE_SOURCE_REPLAY_SKIPPED,
    SEVERITY_INFO,
)
from bankflow.db import check_connection, get_connection
from bankflow.generator.defects import DefectConfig
from bankflow.generator.generator import SyntheticDataGenerator
from bankflow.staging.loader import StagingLoader
from bankflow.staging.schema import init_staging_schema
from bankflow.validation.schema import init_validation_schema
from bankflow.validation.validator import ValidationEngine
from bankflow.warehouse.loader import WarehouseLoader
from bankflow.warehouse.models import ReconciliationReport, WarehouseLoadingSummary
from bankflow.warehouse.reconciliation import ReconciliationEngine
from bankflow.warehouse.schema import init_warehouse_schema


@pytest.fixture
def postgres_test_db():
    """Ensure dedicated test database is accessible and initialize all schemas."""
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
        init_warehouse_schema(conn)

    return test_db


@pytest.fixture(autouse=True)
def clean_warehouse_tables(postgres_test_db):
    """Ensure warehouse transactional and dimensional tables are cleared between tests for test isolation."""
    postgres_test_db.assert_safe_for_reset()
    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM warehouse.fact_transactions WHERE transaction_key > 0;")
            cur.execute("DELETE FROM warehouse.dim_account WHERE account_key > 0;")
            cur.execute("DELETE FROM warehouse.dim_customer WHERE customer_key > 0;")
            cur.execute("DELETE FROM warehouse.dim_branch WHERE branch_key > 0;")
        conn.commit()
    yield


@pytest.mark.integration
def test_warehouse_schema_initialization(postgres_test_db):
    """Verify warehouse schema, dimensions, and facts tables exist and are idempotent."""
    with get_connection(postgres_test_db) as conn:
        # Run init twice to verify idempotency
        init_warehouse_schema(conn)
        init_warehouse_schema(conn)

        with conn.cursor() as cur:
            # Check dim_date
            cur.execute("SELECT count(*) FROM warehouse.dim_date WHERE year_number = 2026;")
            assert cur.fetchone()[0] == 365

            # Check dim_transaction_type seeded values
            cur.execute("SELECT count(*) FROM warehouse.dim_transaction_type;")
            assert cur.fetchone()[0] == 6

            # Verify tables exist
            tables = ["dim_branch", "dim_customer", "dim_account", "fact_transactions"]
            for table in tables:
                cur.execute("""
                    SELECT count(*)
                    FROM information_schema.tables
                    WHERE table_schema = 'warehouse' AND table_name = %s;
                """, (table,))
                assert cur.fetchone()[0] == 1, f"Table warehouse.{table} does not exist"


@pytest.mark.integration
def test_warehouse_clean_batch_loading_and_reconciliation(postgres_test_db, tmp_path):
    """Verify loading a clean batch populates all dimensions, facts, and passes reconciliation."""
    generator = SyntheticDataGenerator(seed=101, defect_config=DefectConfig.clean())
    dataset_dir = tmp_path / "clean_data"
    generator.export_all(
        output_dir=dataset_dir,
        num_branches=3,
        num_customers=10,
        num_accounts=15,
        num_transactions=50,
    )

    batch_id = f"batch-clean-{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        # 1. Stage
        stg_loader = StagingLoader(conn)
        stg_result = stg_loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id)
        assert stg_result["status"] == BATCH_STATUS_SUCCEEDED

        # 2. Validate
        val_engine = ValidationEngine(conn)
        val_summary = val_engine.validate_batch(batch_id)
        assert val_summary.batch_status == BATCH_STATUS_SUCCEEDED
        assert val_summary.records_rejected == 0
        assert val_summary.records_valid == (3 + 10 + 15 + 50)

        # 3. Load
        wh_loader = WarehouseLoader(conn)
        summary = wh_loader.load_batch(batch_id)

        assert summary.status == BATCH_STATUS_SUCCEEDED
        assert summary.branches_loaded == 3
        assert summary.customers_loaded == 10
        assert summary.accounts_loaded == 15
        assert summary.records_inserted == 50
        assert summary.records_skipped == 0
        assert summary.reconciliation_status == "RECONCILED"

        # 4. Verify warehouse rows directly
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM warehouse.dim_branch;")
            assert cur.fetchone()[0] >= 3

            cur.execute("SELECT count(*) FROM warehouse.dim_customer;")
            assert cur.fetchone()[0] >= 10

            cur.execute("SELECT count(*) FROM warehouse.dim_account;")
            assert cur.fetchone()[0] >= 15

            cur.execute("""
                SELECT count(*), count(DISTINCT transaction_id), count(DISTINCT account_key)
                FROM warehouse.fact_transactions
                WHERE source_batch_id = %s;
            """, (batch_id,))
            fact_count, distinct_tids, distinct_accs = cur.fetchone()
            assert fact_count == 50
            assert distinct_tids == 50
            assert distinct_accs > 0

            # Verify date_key resolution aligns with transaction timestamp
            cur.execute("""
                SELECT ft.date_key, TO_CHAR(ft.transaction_timestamp AT TIME ZONE 'UTC', 'YYYYMMDD')::INT
                FROM warehouse.fact_transactions ft
                WHERE ft.source_batch_id = %s
                LIMIT 5;
            """, (batch_id,))
            for d_key, expected_d_key in cur.fetchall():
                assert d_key == expected_d_key


@pytest.mark.integration
def test_warehouse_idempotency_and_replay_safety(postgres_test_db, tmp_path):
    """Verify loading the same batch or identical source events is idempotent and records replays."""
    generator = SyntheticDataGenerator(seed=202, defect_config=DefectConfig.clean())
    dataset_dir = tmp_path / "replay_data"
    generator.export_all(
        output_dir=dataset_dir,
        num_branches=2,
        num_customers=5,
        num_accounts=8,
        num_transactions=25,
    )

    batch_id_1 = f"batch-replay-1-{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        # First load
        stg_loader = StagingLoader(conn)
        stg_loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id_1)
        val_engine = ValidationEngine(conn)
        val_engine.validate_batch(batch_id_1)
        wh_loader = WarehouseLoader(conn)
        summary_1 = wh_loader.load_batch(batch_id_1)

        assert summary_1.records_inserted == 25
        assert summary_1.records_skipped == 0
        assert summary_1.reconciliation_status == "RECONCILED"

        # Second load of the exact same batch
        summary_replay = wh_loader.load_batch(batch_id_1)
        assert summary_replay.records_inserted == 0
        assert summary_replay.records_skipped == 25
        assert summary_replay.reconciliation_status == "RECONCILED"

        # Verify fact_transactions count is still 25, not 50
        with conn.cursor() as cur:
            cur.execute("""
                SELECT count(*)
                FROM warehouse.fact_transactions
                WHERE source_batch_id = %s;
            """, (batch_id_1,))
            assert cur.fetchone()[0] == 25

            # Verify INFO quality issues for RULE_SOURCE_REPLAY_SKIPPED
            cur.execute("""
                SELECT count(*), disposition, severity
                FROM monitoring.data_quality_issues
                WHERE batch_id = %s AND rule_code = %s
                GROUP BY disposition, severity;
            """, (batch_id_1, RULE_SOURCE_REPLAY_SKIPPED))
            issue_count, disp, sev = cur.fetchone()
            assert issue_count == 25
            assert disp == DISPOSITION_SKIPPED
            assert sev == SEVERITY_INFO


@pytest.mark.integration
def test_warehouse_lifecycle_guard_rejects_ineligible_batches(postgres_test_db):
    """Verify WarehouseLoader strictly rejects batches that are FAILED, RUNNING, or unvalidated."""
    with get_connection(postgres_test_db) as conn:
        wh_loader = WarehouseLoader(conn)

        # 1. Non-existent batch
        with pytest.raises(ValueError, match="not found in monitoring.etl_batch_runs"):
            wh_loader.load_batch("non-existent-batch-uuid")

        # 2. Failed batch
        b_failed = f"b-fail-{uuid.uuid4().hex[:8]}"
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO monitoring.etl_batch_runs (batch_id, source_name, status, started_at)
                VALUES (%s, 'test_fail', %s, CURRENT_TIMESTAMP);
            """, (b_failed, BATCH_STATUS_FAILED))
        conn.commit()

        with pytest.raises(ValueError, match="is in FAILED status"):
            wh_loader.load_batch(b_failed)

        # 3. Running batch
        b_run = f"b-run-{uuid.uuid4().hex[:8]}"
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO monitoring.etl_batch_runs (batch_id, source_name, status, started_at)
                VALUES (%s, 'test_run', %s, CURRENT_TIMESTAMP);
            """, (b_run, BATCH_STATUS_RUNNING))
        conn.commit()

        with pytest.raises(ValueError, match="has not completed staging/validation"):
            wh_loader.load_batch(b_run)

        # 4. Batch with SUCCEEDED status but validated_at IS NULL
        b_unval = f"b-unval-{uuid.uuid4().hex[:8]}"
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO monitoring.etl_batch_runs (batch_id, source_name, status, started_at, validated_at)
                VALUES (%s, 'test_unval', %s, CURRENT_TIMESTAMP, NULL);
            """, (b_unval, BATCH_STATUS_SUCCEEDED))
        conn.commit()

        with pytest.raises(ValueError, match="has not been validated"):
            wh_loader.load_batch(b_unval)


@pytest.mark.integration
def test_warehouse_transactional_rollback_on_failure(postgres_test_db, tmp_path):
    """Verify an error during warehouse loading causes a complete rollback with zero partial facts."""
    generator = SyntheticDataGenerator(seed=303, defect_config=DefectConfig.clean())
    dataset_dir = tmp_path / "rollback_data"
    generator.export_all(
        output_dir=dataset_dir,
        num_branches=2,
        num_customers=5,
        num_accounts=5,
        num_transactions=20,
    )

    batch_id = f"batch-rollback-{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        stg_loader = StagingLoader(conn)
        stg_loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id)
        val_engine = ValidationEngine(conn)
        val_engine.validate_batch(batch_id)

        wh_loader = WarehouseLoader(conn)

        # Force a failure inside _load_facts during execution
        with patch.object(wh_loader, "_load_facts", side_effect=RuntimeError("Simulated database failure during fact load")):
            with pytest.raises(RuntimeError, match="Simulated database failure"):
                wh_loader.load_batch(batch_id)

        # Verify nothing from this batch committed to fact_transactions
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM warehouse.fact_transactions WHERE source_batch_id = %s;", (batch_id,))
            assert cur.fetchone()[0] == 0


@pytest.mark.integration
def test_warehouse_reconciliation_detects_discrepancy(postgres_test_db, tmp_path):
    """Verify ReconciliationEngine flags mismatches when counts or monetary values do not reconcile."""
    generator = SyntheticDataGenerator(seed=404, defect_config=DefectConfig.clean())
    dataset_dir = tmp_path / "recon_data"
    generator.export_all(
        output_dir=dataset_dir,
        num_branches=2,
        num_customers=4,
        num_accounts=6,
        num_transactions=15,
    )

    batch_id = f"batch-recon-test-{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        stg_loader = StagingLoader(conn)
        stg_loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id)
        val_engine = ValidationEngine(conn)
        val_engine.validate_batch(batch_id)
        wh_loader = WarehouseLoader(conn)
        wh_loader.load_batch(batch_id)

        recon_engine = ReconciliationEngine(conn)
        clean_report = recon_engine.reconcile_batch(batch_id)
        assert clean_report.is_reconciled is True

        # Now artificially tamper with records_valid in monitoring.etl_batch_runs
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE monitoring.etl_batch_runs
                SET records_valid = records_valid + 99
                WHERE batch_id = %s;
            """, (batch_id,))
        conn.commit()

        # Run reconciliation audit again
        tampered_report = recon_engine.reconcile_batch(batch_id)
        assert tampered_report.is_reconciled is False
        assert len(tampered_report.discrepancies) > 0
        assert any("count mismatch" in d.lower() for d in tampered_report.discrepancies)

        # Verify status in monitoring.etl_batch_runs is UNRECONCILED
        with conn.cursor() as cur:
            cur.execute("SELECT reconciliation_status FROM monitoring.etl_batch_runs WHERE batch_id = %s;", (batch_id,))
            assert cur.fetchone()[0] == "UNRECONCILED"


@pytest.mark.integration
def test_warehouse_defective_batch_loading(postgres_test_db, tmp_path):
    """Verify a defective batch populates only valid records and preserves quarantine boundary."""
    generator = SyntheticDataGenerator(seed=505, defect_config=DefectConfig.standard_test_defects())
    dataset_dir = tmp_path / "defective_data"
    generator.export_all(
        output_dir=dataset_dir,
        num_branches=3,
        num_customers=10,
        num_accounts=15,
        num_transactions=40,
    )

    batch_id = f"batch-defect-wh-{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        stg_loader = StagingLoader(conn)
        stg_loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id)

        val_engine = ValidationEngine(conn)
        val_summary = val_engine.validate_batch(batch_id)
        assert val_summary.batch_status == BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS
        assert val_summary.records_rejected > 0

        wh_loader = WarehouseLoader(conn)
        wh_summary = wh_loader.load_batch(batch_id)

        assert wh_summary.status == BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS
        assert wh_summary.records_inserted > 0
        assert wh_summary.reconciliation_status == "RECONCILED"

        # Verify no quarantined transaction entered warehouse.fact_transactions
        with conn.cursor() as cur:
            cur.execute("""
                SELECT count(*)
                FROM warehouse.fact_transactions ft
                JOIN quarantine.quarantined_records qr ON ft.source_row_id = qr.source_row_id
                WHERE ft.source_batch_id = %s;
            """, (batch_id,))
            assert cur.fetchone()[0] == 0


@pytest.mark.integration
def test_cli_warehouse_commands(postgres_test_db, tmp_path):
    """Verify CLI commands 'load', 'reconcile', 'batch-status', and 'run' work end-to-end."""
    generator = SyntheticDataGenerator(seed=606, defect_config=DefectConfig.clean())
    dataset_dir = tmp_path / "cli_wh_data"
    generator.export_all(
        output_dir=dataset_dir,
        num_branches=2,
        num_customers=5,
        num_accounts=8,
        num_transactions=20,
    )

    runner = CliRunner()
    batch_id = f"batch-cli-{uuid.uuid4().hex[:8]}"

    # Step 1: Stage
    stage_res = runner.invoke(cli, ["stage", "--input-dir", str(dataset_dir), "--batch-id", batch_id, "--test-db"])
    assert stage_res.exit_code == 0
    assert "staging succeeded" in stage_res.output

    # Step 2: Validate
    val_res = runner.invoke(cli, ["validate", batch_id, "--test-db"])
    assert val_res.exit_code == 0
    assert "Validation completed" in val_res.output

    # Step 3: Load CLI
    load_res = runner.invoke(cli, ["load", batch_id, "--test-db"])
    assert load_res.exit_code == 0
    assert "Warehouse loading completed" in load_res.output
    assert "Inserted:  20" in load_res.output

    # Step 4: Reconcile CLI
    recon_res = runner.invoke(cli, ["reconcile", batch_id, "--test-db"])
    assert recon_res.exit_code == 0
    assert "[RECONCILED]" in recon_res.output

    # Step 5: Batch-status CLI
    status_res = runner.invoke(cli, ["batch-status", batch_id, "--test-db"])
    assert status_res.exit_code == 0
    assert "Records Inserted:   20" in status_res.output
    assert "Reconciliation:     RECONCILED" in status_res.output

    # Step 6: Full Pipeline CLI 'run'
    pipeline_dir = tmp_path / "pipeline_run_data"
    generator.export_all(
        output_dir=pipeline_dir,
        num_branches=2,
        num_customers=4,
        num_accounts=6,
        num_transactions=15,
    )
    p_batch_id = f"batch-pipe-{uuid.uuid4().hex[:8]}"
    run_res = runner.invoke(cli, ["run", "--input-dir", str(pipeline_dir), "--batch-id", p_batch_id, "--test-db"])
    assert run_res.exit_code == 0
    assert "[RECONCILED] Pipeline run for batch" in run_res.output
