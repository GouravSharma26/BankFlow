"""
Live PostgreSQL integration tests for BankFlow Phase 3:
Warehouse Schema, Dimensional Loading, Database Idempotency, and Reconciliation.
"""

import os
import threading
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
    DISPOSITION_REJECTED,
    DISPOSITION_SKIPPED,
    RULE_AMOUNT_RULE_VIOLATION,
    RULE_CONFLICTING_REPLAY_PAYLOAD,
    RULE_SOURCE_REPLAY_SKIPPED,
    SEVERITY_ERROR,
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

        with pytest.raises(ValueError, match="ineligible status 'FAILED'"):
            wh_loader.load_batch(b_failed)

        # 3. Running batch
        b_run = f"b-run-{uuid.uuid4().hex[:8]}"
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO monitoring.etl_batch_runs (batch_id, source_name, status, started_at)
                VALUES (%s, 'test_run', %s, CURRENT_TIMESTAMP);
            """, (b_run, BATCH_STATUS_RUNNING))
        conn.commit()

        with pytest.raises(ValueError, match="ineligible status 'RUNNING'"):
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

        # 5. Unsupported status with validated_at populated (Finding 6)
        b_unsupp = f"b-unsupp-{uuid.uuid4().hex[:8]}"
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO monitoring.etl_batch_runs (batch_id, source_name, status, started_at, validated_at)
                VALUES (%s, 'test_unsupp', 'CANCELLED', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP);
            """, (b_unsupp,))
        conn.commit()

        with pytest.raises(ValueError, match="ineligible status 'CANCELLED'"):
            wh_loader.load_batch(b_unsupp)


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


@pytest.mark.integration
def test_cli_full_pipeline_run(postgres_test_db, tmp_path):
    """Verify that the CLI 'run' command executes stage, validate, load, and reconcile end-to-end."""
    generator = SyntheticDataGenerator(seed=707, defect_config=DefectConfig.clean())
    pipeline_dir = tmp_path / "pipeline_run_data"
    generator.export_all(
        output_dir=pipeline_dir,
        num_branches=2,
        num_customers=4,
        num_accounts=6,
        num_transactions=15,
    )
    runner = CliRunner()
    p_batch_id = f"batch-pipe-{uuid.uuid4().hex[:8]}"
    run_res = runner.invoke(cli, ["run", "--input-dir", str(pipeline_dir), "--batch-id", p_batch_id, "--test-db"])
    assert run_res.exit_code == 0
    assert "[RECONCILED] Pipeline run for batch" in run_res.output


@pytest.mark.integration
def test_warehouse_whitespace_normalized_joins_and_loading(postgres_test_db, tmp_path):
    """Verify that entities and transactions with leading/trailing whitespace join and load properly."""
    dataset_dir = tmp_path / "whitespace_data"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    # 1. Write CSVs with padded whitespace in IDs and type fields
    branches_csv = dataset_dir / "branches.csv"
    branches_csv.write_text("branch_id,branch_name,region\n  BR-WS-1  ,  West Branch  ,  WEST  \n", encoding="utf-8")

    customers_csv = dataset_dir / "customers.csv"
    customers_csv.write_text("customer_id,customer_segment,created_date,customer_status\n  CUST-WS-1  ,  RETAIL  ,2026-01-01,  ACTIVE  \n", encoding="utf-8")

    accounts_csv = dataset_dir / "accounts.csv"
    accounts_csv.write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\n  ACC-WS-1  ,  CUST-WS-1  ,  BR-WS-1  ,  CHECKING  ,  OPEN  ,2026-01-01,  USD  \n", encoding="utf-8")

    transactions_csv = dataset_dir / "transactions.csv"
    transactions_csv.write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "  TXN-WS-1  ,  ACC-WS-1  ,  DEPOSIT  ,100.50,  USD  ,2026-02-15T10:00:00+00:00,  COMPLETED  ,  ONLINE  ,,  CORE  \n",
        encoding="utf-8"
    )

    batch_id = f"batch-ws-{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id)

        val_engine = ValidationEngine(conn)
        val_summary = val_engine.validate_batch(batch_id)
        assert val_summary.batch_status == BATCH_STATUS_SUCCEEDED
        assert val_summary.records_rejected == 0

        wh_loader = WarehouseLoader(conn)
        summary = wh_loader.load_batch(batch_id)

        assert summary.branches_loaded == 1
        assert summary.customers_loaded == 1
        assert summary.accounts_loaded == 1
        assert summary.records_inserted == 1
        assert summary.reconciliation_status == "RECONCILED"

        # Direct SQL assertions: check that canonical values in warehouse dimensions are clean
        with conn.cursor() as cur:
            cur.execute("SELECT branch_id, branch_name FROM warehouse.dim_branch WHERE branch_id = 'BR-WS-1';")
            assert cur.fetchone() == ("BR-WS-1", "West Branch")

            cur.execute("SELECT customer_id, customer_segment FROM warehouse.dim_customer WHERE customer_id = 'CUST-WS-1';")
            assert cur.fetchone() == ("CUST-WS-1", "RETAIL")

            cur.execute("SELECT account_id, currency FROM warehouse.dim_account WHERE account_id = 'ACC-WS-1';")
            assert cur.fetchone() == ("ACC-WS-1", "USD")

            cur.execute("SELECT transaction_id, amount, currency, status FROM warehouse.fact_transactions WHERE transaction_id = 'TXN-WS-1';")
            row = cur.fetchone()
            assert row[0] == "TXN-WS-1"
            assert row[1] == Decimal("100.50")
            assert row[2] == "USD"
            assert row[3] == "COMPLETED"


@pytest.mark.integration
def test_warehouse_conflicting_replay_payload_rejected_and_quarantined(postgres_test_db, tmp_path):
    """Verify that a replay with a conflicting payload is rejected as an error, quarantined, and fails reconciliation."""
    dataset_dir_1 = tmp_path / "replay_orig"
    dataset_dir_1.mkdir(parents=True, exist_ok=True)
    (dataset_dir_1 / "branches.csv").write_text("branch_id,branch_name,region\nBR-R1,Branch 1,WEST\n", encoding="utf-8")
    (dataset_dir_1 / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-R1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
    (dataset_dir_1 / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-R1,CUST-R1,BR-R1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
    (dataset_dir_1 / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-CONFL-1,ACC-R1,DEPOSIT,100.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8"
    )

    batch_1 = f"batch-replay-orig-{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        loader.ingest_dataset_directory(dataset_dir_1, batch_id=batch_1)
        val_engine = ValidationEngine(conn)
        val_engine.validate_batch(batch_1)
        wh_loader = WarehouseLoader(conn)
        summary_1 = wh_loader.load_batch(batch_1)
        assert summary_1.records_inserted == 1
        assert summary_1.reconciliation_status == "RECONCILED"

        # Batch 2: same (source_system, transaction_id), but CONFLICTING amount: 250.00
        dataset_dir_2 = tmp_path / "replay_conflict"
        dataset_dir_2.mkdir(parents=True, exist_ok=True)
        (dataset_dir_2 / "branches.csv").write_text("branch_id,branch_name,region\nBR-R1,Branch 1,WEST\n", encoding="utf-8")
        (dataset_dir_2 / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-R1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
        (dataset_dir_2 / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-R1,CUST-R1,BR-R1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
        (dataset_dir_2 / "transactions.csv").write_text(
            "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
            "TXN-CONFL-1,ACC-R1,DEPOSIT,250.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
            encoding="utf-8"
        )

        batch_2 = f"batch-replay-confl-{uuid.uuid4().hex[:8]}"
        loader.ingest_dataset_directory(dataset_dir_2, batch_id=batch_2)
        val_engine.validate_batch(batch_2)

        summary_2 = wh_loader.load_batch(batch_2)
        # Verify conflicting replay is NOT counted as inserted or successfully skipped!
        assert summary_2.records_inserted == 0
        assert summary_2.records_skipped == 0
        assert summary_2.conflicting_replays == 1
        assert summary_2.reconciliation_status == "UNRECONCILED"

        # Verify error issue logged in monitoring.data_quality_issues
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rule_code, severity, disposition, reason
                FROM monitoring.data_quality_issues
                WHERE batch_id = %s AND rule_code = %s;
            """, (batch_2, RULE_CONFLICTING_REPLAY_PAYLOAD))
            issue = cur.fetchone()
            assert issue is not None
            assert issue[0] == RULE_CONFLICTING_REPLAY_PAYLOAD
            assert issue[1] == SEVERITY_ERROR
            assert issue[2] == DISPOSITION_REJECTED
            assert "Conflicting replay" in issue[3]

            # Verify quarantined in quarantine.quarantined_records
            cur.execute("""
                SELECT count(*)
                FROM quarantine.quarantined_records
                WHERE batch_id = %s AND primary_rule_code = %s;
            """, (batch_2, RULE_CONFLICTING_REPLAY_PAYLOAD))
            assert cur.fetchone()[0] == 1


@pytest.mark.integration
def test_cli_unreconciled_returns_nonzero_exit_code(postgres_test_db, tmp_path):
    """Verify that CLI commands 'reconcile', 'load', and 'run' return exit code 1 when reconciliation fails."""
    dataset_dir = tmp_path / "cli_unrec_data"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "branches.csv").write_text("branch_id,branch_name,region\nBR-U1,Branch U,NORTH\n", encoding="utf-8")
    (dataset_dir / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-U1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
    (dataset_dir / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-U1,CUST-U1,BR-U1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
    (dataset_dir / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-U1,ACC-U1,DEPOSIT,50.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8"
    )

    runner = CliRunner()
    batch_id = f"batch-cli-unrec-{uuid.uuid4().hex[:8]}"

    # Stage & validate
    runner.invoke(cli, ["stage", "--input-dir", str(dataset_dir), "--batch-id", batch_id, "--test-db"])
    runner.invoke(cli, ["validate", batch_id, "--test-db"])

    # Load into warehouse
    load_res = runner.invoke(cli, ["load", batch_id, "--test-db"])
    assert load_res.exit_code == 0

    # Tamper with staging records_valid to induce reconciliation failure
    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE monitoring.etl_batch_runs SET records_valid = records_valid + 50 WHERE batch_id = %s;", (batch_id,))
        conn.commit()

    # 1. Reconcile CLI command must return exit code 1
    reconcile_res = runner.invoke(cli, ["reconcile", batch_id, "--test-db"])
    assert reconcile_res.exit_code != 0
    assert "[UNRECONCILED]" in reconcile_res.output

    # 2. Load CLI command on a batch with conflicting replays must return exit code 1
    conflict_dir = tmp_path / "cli_unrec_conflict"
    conflict_dir.mkdir(parents=True, exist_ok=True)
    (conflict_dir / "branches.csv").write_text("branch_id,branch_name,region\nBR-U1,Branch U,NORTH\n", encoding="utf-8")
    (conflict_dir / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-U1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
    (conflict_dir / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-U1,CUST-U1,BR-U1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
    (conflict_dir / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-U1,ACC-U1,DEPOSIT,999.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8"
    )
    b_conf = f"batch-cli-conf-{uuid.uuid4().hex[:8]}"
    runner.invoke(cli, ["stage", "--input-dir", str(conflict_dir), "--batch-id", b_conf, "--test-db"])
    runner.invoke(cli, ["validate", b_conf, "--test-db"])
    load_conf_res = runner.invoke(cli, ["load", b_conf, "--test-db"])
    assert load_conf_res.exit_code != 0
    assert "UNRECONCILED" in load_conf_res.output

    # 3. Full pipeline run on a batch with conflicting replays must return exit code 1
    b_run_conf = f"batch-pipe-conf-{uuid.uuid4().hex[:8]}"
    run_conf_res = runner.invoke(cli, ["run", "--input-dir", str(conflict_dir), "--batch-id", b_run_conf, "--test-db"])
    assert run_conf_res.exit_code != 0
    assert "UNRECONCILED" in run_conf_res.output


@pytest.mark.integration
def test_amount_with_more_than_two_decimals_rejected_in_integration(postgres_test_db, tmp_path):
    """Verify that an amount with >2 decimal places (10.001) is quarantined and never loaded into facts."""
    dataset_dir = tmp_path / "scale_data"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "branches.csv").write_text("branch_id,branch_name,region\nBR-S1,Branch S,EAST\n", encoding="utf-8")
    (dataset_dir / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-S1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
    (dataset_dir / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-S1,CUST-S1,BR-S1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
    (dataset_dir / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-SCALE-1,ACC-S1,DEPOSIT,10.001,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8"
    )

    batch_id = f"batch-scale-{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id)

        val_engine = ValidationEngine(conn)
        val_summary = val_engine.validate_batch(batch_id)
        assert val_summary.records_rejected == 1

        # Check quarantine
        with conn.cursor() as cur:
            cur.execute("""
                SELECT primary_rule_code FROM quarantine.quarantined_records
                WHERE batch_id = %s;
            """, (batch_id,))
            assert cur.fetchone()[0] == RULE_AMOUNT_RULE_VIOLATION

        # Load into warehouse: fact must not be inserted
        wh_loader = WarehouseLoader(conn)
        wh_summary = wh_loader.load_batch(batch_id)
        assert wh_summary.records_inserted == 0

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM warehouse.fact_transactions WHERE transaction_id = 'TXN-SCALE-1';")
            assert cur.fetchone()[0] == 0


@pytest.mark.integration
def test_warehouse_historical_dimension_dependency_preflight_guard(postgres_test_db, tmp_path):
    """Verify preflight stops load if a batch references accounts from an unloaded upstream batch."""
    dataset_dir_1 = tmp_path / "upstream_data"
    dataset_dir_1.mkdir(parents=True, exist_ok=True)
    (dataset_dir_1 / "branches.csv").write_text("branch_id,branch_name,region\nBR-PRE-1,Branch Pre,WEST\n", encoding="utf-8")
    (dataset_dir_1 / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-PRE-1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
    (dataset_dir_1 / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-PRE-1,CUST-PRE-1,BR-PRE-1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
    (dataset_dir_1 / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-PRE-1,ACC-PRE-1,DEPOSIT,50.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8"
    )

    batch_1 = f"batch-preflight-1-{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        loader.ingest_dataset_directory(dataset_dir_1, batch_id=batch_1)
        val_engine = ValidationEngine(conn)
        val_engine.validate_batch(batch_1)
        # Note: Batch 1 is validated, but NOT loaded into warehouse!

        # Batch 2: has a transaction referencing ACC-PRE-1 from Batch 1
        dataset_dir_2 = tmp_path / "downstream_data"
        dataset_dir_2.mkdir(parents=True, exist_ok=True)
        (dataset_dir_2 / "branches.csv").write_text("branch_id,branch_name,region\nBR-PRE-2,Branch Pre 2,EAST\n", encoding="utf-8")
        (dataset_dir_2 / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-PRE-2,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
        (dataset_dir_2 / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-PRE-2,CUST-PRE-2,BR-PRE-2,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
        (dataset_dir_2 / "transactions.csv").write_text(
            "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
            "TXN-PRE-2,ACC-PRE-1,DEPOSIT,88.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
            encoding="utf-8"
        )

        batch_2 = f"batch-preflight-2-{uuid.uuid4().hex[:8]}"
        loader.ingest_dataset_directory(dataset_dir_2, batch_id=batch_2)
        val_summary_2 = val_engine.validate_batch(batch_2)
        assert val_summary_2.records_valid > 0

        # Attempt to load Batch 2: MUST fail preflight because ACC-PRE-1 is not in warehouse!
        wh_loader = WarehouseLoader(conn)
        with pytest.raises(ValueError, match="preflight check failed.*ACC-PRE-1"):
            wh_loader.load_batch(batch_2)

        # Now load Batch 1 into the warehouse
        wh_loader.load_batch(batch_1)

        # Now loading Batch 2 MUST succeed!
        summary_2 = wh_loader.load_batch(batch_2)
        assert summary_2.records_inserted == 1
        assert summary_2.reconciliation_status == "RECONCILED"


@pytest.mark.integration
def test_warehouse_extended_date_dimension_support(postgres_test_db, tmp_path):
    """Verify that dates outside the initial 2020-2035 range (e.g. 2018 or 2038) dynamically extend dim_date and load successfully."""
    dataset_dir = tmp_path / "date_ext_data"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    (dataset_dir / "branches.csv").write_text("branch_id,branch_name,region\nBR-D1,Branch D,NORTH\n", encoding="utf-8")
    (dataset_dir / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-D1,RETAIL,2018-01-01,ACTIVE\n", encoding="utf-8")
    (dataset_dir / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-D1,CUST-D1,BR-D1,CHECKING,OPEN,2018-01-01,USD\n", encoding="utf-8")
    (dataset_dir / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-PAST-1,ACC-D1,DEPOSIT,50.00,USD,2014-05-20T10:00:00+00:00,COMPLETED,ONLINE,,CORE\n"
        "TXN-FUTURE-1,ACC-D1,DEPOSIT,75.00,USD,2042-08-10T10:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8"
    )

    batch_id = f"batch-date-ext-{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id)

        val_engine = ValidationEngine(conn)
        val_engine.validate_batch(batch_id)

        wh_loader = WarehouseLoader(conn)
        summary = wh_loader.load_batch(batch_id)

        assert summary.records_inserted == 2
        assert summary.reconciliation_status == "RECONCILED"

        with conn.cursor() as cur:
            cur.execute("SELECT date_key FROM warehouse.fact_transactions WHERE transaction_id = 'TXN-PAST-1';")
            assert cur.fetchone()[0] == 20140520

            cur.execute("SELECT date_key FROM warehouse.fact_transactions WHERE transaction_id = 'TXN-FUTURE-1';")
            assert cur.fetchone()[0] == 20420810


@pytest.mark.integration
def test_warehouse_conflicting_replay_changed_type_and_channel_independently(postgres_test_db, tmp_path):
    """
    Verify that an existing event replayed with:
    1. Changed transaction_type (DEPOSIT -> WITHDRAWAL)
    2. Changed channel (ONLINE -> ATM)
    are independently classified as RULE_CONFLICTING_REPLAY_PAYLOAD, quarantined, and fail reconciliation.
    Also verifies that an identical replay is accepted and skipped safely.
    """
    # 1. Base batch (original event: DEPOSIT, ONLINE)
    dataset_dir_1 = tmp_path / "replay_base"
    dataset_dir_1.mkdir(parents=True, exist_ok=True)
    (dataset_dir_1 / "branches.csv").write_text("branch_id,branch_name,region\nBR-IND-1,Branch Ind,WEST\n", encoding="utf-8")
    (dataset_dir_1 / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-IND-1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
    (dataset_dir_1 / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-IND-1,CUST-IND-1,BR-IND-1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
    (dataset_dir_1 / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-IND-1,ACC-IND-1,DEPOSIT,100.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8"
    )

    batch_1 = f"batch-ind-1-{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        val = ValidationEngine(conn)
        wh = WarehouseLoader(conn)

        loader.ingest_dataset_directory(dataset_dir_1, batch_id=batch_1)
        val.validate_batch(batch_1)
        summary_1 = wh.load_batch(batch_1)
        assert summary_1.records_inserted == 1
        assert summary_1.reconciliation_status == "RECONCILED"

        # 2. Batch 2: Changed transaction_type independently (WITHDRAWAL instead of DEPOSIT)
        dataset_dir_2 = tmp_path / "replay_changed_type"
        dataset_dir_2.mkdir(parents=True, exist_ok=True)
        (dataset_dir_2 / "branches.csv").write_text("branch_id,branch_name,region\nBR-IND-1,Branch Ind,WEST\n", encoding="utf-8")
        (dataset_dir_2 / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-IND-1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
        (dataset_dir_2 / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-IND-1,CUST-IND-1,BR-IND-1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
        (dataset_dir_2 / "transactions.csv").write_text(
            "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
            "TXN-IND-1,ACC-IND-1,WITHDRAWAL,100.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
            encoding="utf-8"
        )
        batch_2 = f"batch-ind-2-{uuid.uuid4().hex[:8]}"
        loader.ingest_dataset_directory(dataset_dir_2, batch_id=batch_2)
        val.validate_batch(batch_2)
        summary_2 = wh.load_batch(batch_2)

        assert summary_2.records_inserted == 0
        assert summary_2.records_skipped == 0
        assert summary_2.conflicting_replays == 1
        assert summary_2.reconciliation_status == "UNRECONCILED"

        with conn.cursor() as cur:
            cur.execute("""
                SELECT rule_code, severity, disposition, reason
                FROM monitoring.data_quality_issues
                WHERE batch_id = %s AND rule_code = %s;
            """, (batch_2, RULE_CONFLICTING_REPLAY_PAYLOAD))
            issue = cur.fetchone()
            assert issue is not None
            assert issue[0] == RULE_CONFLICTING_REPLAY_PAYLOAD
            assert "transaction_type" in issue[3]

            cur.execute("SELECT count(*) FROM quarantine.quarantined_records WHERE batch_id = %s;", (batch_2,))
            assert cur.fetchone()[0] == 1

        # 3. Batch 3: Changed channel independently (ATM instead of ONLINE, with original DEPOSIT)
        dataset_dir_3 = tmp_path / "replay_changed_chan"
        dataset_dir_3.mkdir(parents=True, exist_ok=True)
        (dataset_dir_3 / "branches.csv").write_text("branch_id,branch_name,region\nBR-IND-1,Branch Ind,WEST\n", encoding="utf-8")
        (dataset_dir_3 / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-IND-1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
        (dataset_dir_3 / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-IND-1,CUST-IND-1,BR-IND-1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
        (dataset_dir_3 / "transactions.csv").write_text(
            "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
            "TXN-IND-1,ACC-IND-1,DEPOSIT,100.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ATM,,CORE\n",
            encoding="utf-8"
        )
        batch_3 = f"batch-ind-3-{uuid.uuid4().hex[:8]}"
        loader.ingest_dataset_directory(dataset_dir_3, batch_id=batch_3)
        val.validate_batch(batch_3)
        summary_3 = wh.load_batch(batch_3)

        assert summary_3.records_inserted == 0
        assert summary_3.records_skipped == 0
        assert summary_3.conflicting_replays == 1
        assert summary_3.reconciliation_status == "UNRECONCILED"

        with conn.cursor() as cur:
            cur.execute("""
                SELECT rule_code, severity, disposition, reason
                FROM monitoring.data_quality_issues
                WHERE batch_id = %s AND rule_code = %s;
            """, (batch_3, RULE_CONFLICTING_REPLAY_PAYLOAD))
            issue = cur.fetchone()
            assert issue is not None
            assert issue[0] == RULE_CONFLICTING_REPLAY_PAYLOAD
            assert "channel" in issue[3]

            cur.execute("SELECT count(*) FROM quarantine.quarantined_records WHERE batch_id = %s;", (batch_3,))
            assert cur.fetchone()[0] == 1

        # 4. Batch 4: Identical replay (all fields match original Batch 1)
        dataset_dir_4 = tmp_path / "replay_identical"
        dataset_dir_4.mkdir(parents=True, exist_ok=True)
        (dataset_dir_4 / "branches.csv").write_text("branch_id,branch_name,region\nBR-IND-1,Branch Ind,WEST\n", encoding="utf-8")
        (dataset_dir_4 / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-IND-1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
        (dataset_dir_4 / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-IND-1,CUST-IND-1,BR-IND-1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
        (dataset_dir_4 / "transactions.csv").write_text(
            "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
            "TXN-IND-1,ACC-IND-1,DEPOSIT,100.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
            encoding="utf-8"
        )
        batch_4 = f"batch-ind-4-{uuid.uuid4().hex[:8]}"
        loader.ingest_dataset_directory(dataset_dir_4, batch_id=batch_4)
        val.validate_batch(batch_4)
        summary_4 = wh.load_batch(batch_4)

        assert summary_4.records_inserted == 0
        assert summary_4.records_skipped == 1
        assert summary_4.conflicting_replays == 0
        assert summary_4.reconciliation_status == "RECONCILED"


@pytest.mark.integration
def test_warehouse_concurrent_loads_atomic_replay_safety(postgres_test_db, tmp_path):
    """
    Verify that concurrent warehouse loads across separate database connections:
    1. Do not cause unhandled uniqueness violations.
    2. Atomic INSERT ... ON CONFLICT DO NOTHING ensures exactly 1 fact is created.
    3. The losing concurrent batch correctly classifies the collision as an identical replay
       or a conflicting replay rather than failing.
    """
    # 1. Setup shared dimension files for concurrent identical replay
    dataset_dir_1 = tmp_path / "concurrent_batch_1"
    dataset_dir_1.mkdir(parents=True, exist_ok=True)
    (dataset_dir_1 / "branches.csv").write_text("branch_id,branch_name,region\nBR-CONC-1,Concurrent Branch,WEST\n", encoding="utf-8")
    (dataset_dir_1 / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-CONC-1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
    (dataset_dir_1 / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-CONC-1,CUST-CONC-1,BR-CONC-1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
    (dataset_dir_1 / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-CONC-1,ACC-CONC-1,DEPOSIT,100.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8"
    )

    dataset_dir_2 = tmp_path / "concurrent_batch_2"
    dataset_dir_2.mkdir(parents=True, exist_ok=True)
    (dataset_dir_2 / "branches.csv").write_text("branch_id,branch_name,region\nBR-CONC-1,Concurrent Branch,WEST\n", encoding="utf-8")
    (dataset_dir_2 / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-CONC-1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
    (dataset_dir_2 / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-CONC-1,CUST-CONC-1,BR-CONC-1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
    (dataset_dir_2 / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-CONC-1,ACC-CONC-1,DEPOSIT,100.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8"
    )

    batch_1 = f"batch-conc-1-{uuid.uuid4().hex[:8]}"
    batch_2 = f"batch-conc-2-{uuid.uuid4().hex[:8]}"

    # Ingest and validate both batches
    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        val = ValidationEngine(conn)
        loader.ingest_dataset_directory(dataset_dir_1, batch_id=batch_1)
        val.validate_batch(batch_1)
        loader.ingest_dataset_directory(dataset_dir_2, batch_id=batch_2)
        val.validate_batch(batch_2)

    # Now load both batches CONCURRENTLY using separate connections and threads
    results = {}
    barrier = threading.Barrier(2)

    def worker(b_id, idx):
        try:
            with get_connection(postgres_test_db) as thread_conn:
                wh = WarehouseLoader(thread_conn)
                barrier.wait()
                summary = wh.load_batch(b_id)
                results[idx] = ("success", summary)
        except Exception as exc:
            results[idx] = ("error", exc)

    t1 = threading.Thread(target=worker, args=(batch_1, 1))
    t2 = threading.Thread(target=worker, args=(batch_2, 2))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Neither thread should encounter an unhandled exception or uniqueness error
    assert results[1][0] == "success", f"Thread 1 failed: {results[1][1]}"
    assert results[2][0] == "success", f"Thread 2 failed: {results[2][1]}"

    sum_1 = results[1][1]
    sum_2 = results[2][1]

    # Exactly one thread inserts the fact, and the other safely skips as identical replay
    total_inserted = sum_1.records_inserted + sum_2.records_inserted
    total_skipped = sum_1.records_skipped + sum_2.records_skipped
    assert total_inserted == 1
    assert total_skipped == 1

    # Check warehouse facts: exactly 1 fact exists
    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM warehouse.fact_transactions WHERE transaction_id = 'TXN-CONC-1';")
            assert cur.fetchone()[0] == 1

    # Part B: Concurrent conflicting replays (differing amounts: 500.00 vs 999.00)
    dataset_dir_3 = tmp_path / "concurrent_batch_3"
    dataset_dir_3.mkdir(parents=True, exist_ok=True)
    (dataset_dir_3 / "branches.csv").write_text("branch_id,branch_name,region\nBR-CONC-1,Concurrent Branch,WEST\n", encoding="utf-8")
    (dataset_dir_3 / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-CONC-1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
    (dataset_dir_3 / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-CONC-1,CUST-CONC-1,BR-CONC-1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
    (dataset_dir_3 / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-CONC-2,ACC-CONC-1,DEPOSIT,500.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8"
    )

    dataset_dir_4 = tmp_path / "concurrent_batch_4"
    dataset_dir_4.mkdir(parents=True, exist_ok=True)
    (dataset_dir_4 / "branches.csv").write_text("branch_id,branch_name,region\nBR-CONC-1,Concurrent Branch,WEST\n", encoding="utf-8")
    (dataset_dir_4 / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-CONC-1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
    (dataset_dir_4 / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-CONC-1,CUST-CONC-1,BR-CONC-1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
    (dataset_dir_4 / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-CONC-2,ACC-CONC-1,DEPOSIT,999.00,USD,2026-03-01T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8"
    )

    batch_3 = f"batch-conc-3-{uuid.uuid4().hex[:8]}"
    batch_4 = f"batch-conc-4-{uuid.uuid4().hex[:8]}"

    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        val = ValidationEngine(conn)
        loader.ingest_dataset_directory(dataset_dir_3, batch_id=batch_3)
        val.validate_batch(batch_3)
        loader.ingest_dataset_directory(dataset_dir_4, batch_id=batch_4)
        val.validate_batch(batch_4)

    results_conflict = {}
    barrier_conflict = threading.Barrier(2)

    def worker_conflict(b_id, idx):
        try:
            with get_connection(postgres_test_db) as thread_conn:
                wh = WarehouseLoader(thread_conn)
                barrier_conflict.wait()
                summary = wh.load_batch(b_id)
                results_conflict[idx] = ("success", summary)
        except Exception as exc:
            results_conflict[idx] = ("error", exc)

    t3 = threading.Thread(target=worker_conflict, args=(batch_3, 3))
    t4 = threading.Thread(target=worker_conflict, args=(batch_4, 4))
    t3.start()
    t4.start()
    t3.join()
    t4.join()

    assert results_conflict[3][0] == "success", f"Thread 3 failed: {results_conflict[3][1]}"
    assert results_conflict[4][0] == "success", f"Thread 4 failed: {results_conflict[4][1]}"

    sum_3 = results_conflict[3][1]
    sum_4 = results_conflict[4][1]

    # Exactly one thread inserts 1 fact, the other is classified as conflicting replay (0 inserted, 1 conflicting)
    total_inserted_c = sum_3.records_inserted + sum_4.records_inserted
    total_conflicting_c = sum_3.conflicting_replays + sum_4.conflicting_replays
    assert total_inserted_c == 1
    assert total_conflicting_c == 1

    # Exactly 1 fact in warehouse
    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM warehouse.fact_transactions WHERE transaction_id = 'TXN-CONC-2';")
            assert cur.fetchone()[0] == 1
            cur.execute("""
                SELECT count(*) FROM quarantine.quarantined_records
                WHERE primary_rule_code = %s AND batch_id IN (%s, %s);
            """, (RULE_CONFLICTING_REPLAY_PAYLOAD, batch_3, batch_4))
            assert cur.fetchone()[0] == 1
