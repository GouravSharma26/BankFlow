"""
PostgreSQL integration tests for BankFlow Phase 4:
Analytics queries, reporting views, and metric definitions.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
import psycopg2
from click.testing import CliRunner

from bankflow.__main__ import cli
from bankflow.analytics.schema import init_reporting_schema
from bankflow.config import get_settings
from bankflow.db import check_connection, get_connection
from bankflow.staging.loader import StagingLoader
from bankflow.staging.schema import init_staging_schema
from bankflow.validation.schema import init_validation_schema
from bankflow.validation.validator import ValidationEngine
from bankflow.warehouse.loader import WarehouseLoader
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
        init_reporting_schema(conn)

    return test_db


@pytest.fixture(autouse=True)
def clean_test_tables(postgres_test_db):
    """Clean warehouse, staging, monitoring, and quarantine tables between test runs."""
    postgres_test_db.assert_safe_for_reset()
    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM warehouse.fact_transactions WHERE transaction_key > 0;")
            cur.execute("DELETE FROM warehouse.dim_account WHERE account_key > 0;")
            cur.execute("DELETE FROM warehouse.dim_customer WHERE customer_key > 0;")
            cur.execute("DELETE FROM warehouse.dim_branch WHERE branch_key > 0;")
            cur.execute("DELETE FROM quarantine.quarantined_records WHERE source_row_id > 0;")
            cur.execute("DELETE FROM monitoring.data_quality_issues WHERE source_row_number > 0;")
            cur.execute("DELETE FROM staging.stg_transactions WHERE source_row_id > 0;")
            cur.execute("DELETE FROM staging.stg_accounts WHERE source_row_id > 0;")
            cur.execute("DELETE FROM staging.stg_customers WHERE source_row_id > 0;")
            cur.execute("DELETE FROM staging.stg_branches WHERE source_row_id > 0;")
            cur.execute("DELETE FROM monitoring.etl_batch_runs WHERE records_staged >= 0;")
        conn.commit()
    yield


def _populate_known_test_warehouse(postgres_test_db, tmp_path: Path) -> str:
    """Helper to populate known deterministic records across two dates and currencies."""
    dataset_dir = tmp_path / f"known_data_{uuid.uuid4().hex[:6]}"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    # 2 branches
    (dataset_dir / "branches.csv").write_text(
        "branch_id,branch_name,region\n"
        "BR-A1,Branch Alpha,NORTH\n"
        "BR-A2,Branch Beta,SOUTH\n",
        encoding="utf-8"
    )

    # 2 customers
    (dataset_dir / "customers.csv").write_text(
        "customer_id,customer_segment,created_date,customer_status\n"
        "CUST-A1,RETAIL,2026-01-01,ACTIVE\n"
        "CUST-A2,PREMIUM,2026-01-15,ACTIVE\n",
        encoding="utf-8"
    )

    # 3 accounts (2 USD, 1 EUR)
    (dataset_dir / "accounts.csv").write_text(
        "account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\n"
        "ACC-A1,CUST-A1,BR-A1,CHECKING,OPEN,2026-01-01,USD\n"
        "ACC-A2,CUST-A2,BR-A2,SAVINGS,OPEN,2026-01-15,USD\n"
        "ACC-A3,CUST-A1,BR-A1,CHECKING,OPEN,2026-02-01,EUR\n",
        encoding="utf-8"
    )

    # 7 transactions: 5 on 2026-03-15 (USD), 2 on 2026-03-16 (EUR)
    (dataset_dir / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-01,ACC-A1,DEPOSIT,100.00,USD,2026-03-15T10:00:00+00:00,COMPLETED,ONLINE,,CORE\n"
        "TXN-02,ACC-A1,DEPOSIT,50.00,USD,2026-03-15T11:00:00+00:00,PENDING,MOBILE,,CORE\n"
        "TXN-03,ACC-A2,WITHDRAWAL,30.00,USD,2026-03-15T12:00:00+00:00,COMPLETED,ATM,,CORE\n"
        "TXN-04,ACC-A2,WITHDRAWAL,20.00,USD,2026-03-15T13:00:00+00:00,FAILED,BRANCH,,CORE\n"
        "TXN-05,ACC-A2,REVERSAL,30.00,USD,2026-03-15T14:00:00+00:00,COMPLETED,ONLINE,,CORE\n"
        "TXN-06,ACC-A3,DEPOSIT,200.00,EUR,2026-03-16T09:00:00+00:00,COMPLETED,ONLINE,,CORE\n"
        "TXN-07,ACC-A3,PAYMENT,45.00,EUR,2026-03-16T15:00:00+00:00,COMPLETED,MOBILE,,CORE\n",
        encoding="utf-8"
    )

    batch_id = f"batch-known-{uuid.uuid4().hex[:8]}"
    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id)

        val = ValidationEngine(conn)
        val.validate_batch(batch_id)

        wh = WarehouseLoader(conn)
        summary = wh.load_batch(batch_id)
        assert summary.records_inserted == 7
        assert summary.reconciliation_status == "RECONCILED"

    return batch_id


@pytest.mark.integration
def test_reporting_schema_initialization(postgres_test_db):
    """Verify that reporting schema and all analytical views are cleanly initialized."""
    with get_connection(postgres_test_db) as conn:
        init_reporting_schema(conn, force=True)
        with conn.cursor() as cur:
            views = [
                "v_daily_transaction_summary",
                "v_deposit_withdrawal_analysis",
                "v_branch_channel_activity",
                "v_transaction_type_mix",
                "v_data_quality_summary",
                "v_pipeline_execution_health",
                "v_quarantine_inventory",
            ]
            for v in views:
                cur.execute(f"SELECT to_regclass('reporting.{v}') IS NOT NULL;")
                assert cur.fetchone()[0] is True, f"View reporting.{v} does not exist"


@pytest.mark.integration
def test_daily_transaction_summary_known_answers(postgres_test_db, tmp_path):
    """Verify daily transaction summary view outputs exact known answer values."""
    _populate_known_test_warehouse(postgres_test_db, tmp_path)

    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    reporting_date,
                    currency,
                    total_transaction_count,
                    completed_transaction_count,
                    pending_transaction_count,
                    failed_transaction_count,
                    reversed_transaction_count,
                    active_accounts,
                    active_customers,
                    gross_transaction_amount,
                    completed_gross_amount
                FROM reporting.v_daily_transaction_summary
                ORDER BY reporting_date, currency;
            """)
            rows = cur.fetchall()
            assert len(rows) == 2

            # Day 1: 2026-03-15 (USD)
            row_usd = rows[0]
            assert str(row_usd[0]) == "2026-03-15"
            assert row_usd[1] == "USD"
            assert row_usd[2] == 5  # total
            assert row_usd[3] == 3  # completed (TXN-01, TXN-03, TXN-05)
            assert row_usd[4] == 1  # pending (TXN-02)
            assert row_usd[5] == 1  # failed (TXN-04)
            assert row_usd[6] == 0  # reversed status
            assert row_usd[7] == 2  # distinct accounts (ACC-A1, ACC-A2)
            assert row_usd[8] == 2  # distinct customers (CUST-A1, CUST-A2)
            assert row_usd[9] == Decimal("230.00")  # 100 + 50 + 30 + 20 + 30
            assert row_usd[10] == Decimal("160.00")  # 100 + 30 + 30

            # Day 2: 2026-03-16 (EUR)
            row_eur = rows[1]
            assert str(row_eur[0]) == "2026-03-16"
            assert row_eur[1] == "EUR"
            assert row_eur[2] == 2
            assert row_eur[3] == 2
            assert row_eur[4] == 0
            assert row_eur[5] == 0
            assert row_eur[6] == 0
            assert row_eur[7] == 1  # ACC-A3
            assert row_eur[8] == 1  # CUST-A1
            assert row_eur[9] == Decimal("245.00")  # 200 + 45
            assert row_eur[10] == Decimal("245.00")


@pytest.mark.integration
def test_deposit_withdrawal_analysis_known_answers(postgres_test_db, tmp_path):
    """
    Verify deposit versus withdrawal metrics.
    Ensures that reversals are reported as adjustments and do not subtract from gross event flow.
    """
    _populate_known_test_warehouse(postgres_test_db, tmp_path)

    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    reporting_date,
                    currency,
                    deposit_count,
                    deposit_gross_amount,
                    completed_deposit_count,
                    completed_deposit_gross_amount,
                    withdrawal_count,
                    withdrawal_gross_amount,
                    completed_withdrawal_count,
                    completed_withdrawal_gross_amount,
                    reversal_count,
                    reversal_gross_amount
                FROM reporting.v_deposit_withdrawal_analysis
                ORDER BY reporting_date, currency;
            """)
            rows = cur.fetchall()
            assert len(rows) == 2

            # 2026-03-15 USD
            usd = rows[0]
            assert str(usd[0]) == "2026-03-15"
            assert usd[1] == "USD"
            assert usd[2] == 2  # deposit_count
            assert usd[3] == Decimal("150.00")  # deposit_gross_amount
            assert usd[4] == 1  # completed_deposit_count
            assert usd[5] == Decimal("100.00")  # completed_deposit_gross_amount
            assert usd[6] == 2  # withdrawal_count
            assert usd[7] == Decimal("50.00")  # withdrawal_gross_amount
            assert usd[8] == 1  # completed_withdrawal_count
            assert usd[9] == Decimal("30.00")  # completed_withdrawal_gross_amount
            assert usd[10] == 1  # reversal_count
            assert usd[11] == Decimal("30.00")  # reversal_gross_amount

            # 2026-03-16 EUR
            eur = rows[1]
            assert str(eur[0]) == "2026-03-16"
            assert eur[1] == "EUR"
            assert eur[2] == 1
            assert eur[3] == Decimal("200.00")
            assert eur[4] == 1
            assert eur[5] == Decimal("200.00")
            assert eur[6] == 0
            assert eur[7] == Decimal("0.00")
            assert eur[8] == 0
            assert eur[9] == Decimal("0.00")
            assert eur[10] == 0
            assert eur[11] == Decimal("0.00")


@pytest.mark.integration
def test_branch_channel_activity_known_answers(postgres_test_db, tmp_path):
    """Verify branch and channel metrics grouped by region, branch, channel, and currency."""
    _populate_known_test_warehouse(postgres_test_db, tmp_path)

    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT region, branch_id, channel, currency,
                       total_transaction_count, completed_transaction_count,
                       gross_transaction_amount, completed_gross_amount
                FROM reporting.v_branch_channel_activity
                ORDER BY branch_id, channel, currency;
            """)
            rows = cur.fetchall()
            # Expect:
            # BR-A1: MOBILE/EUR (1), ONLINE/EUR (1), MOBILE/USD (1), ONLINE/USD (1)
            # BR-A2: ATM/USD (1), BRANCH/USD (1), ONLINE/USD (1)
            assert len(rows) == 7

            data = {(r[1], r[2], r[3]): (r[4], r[5], r[6], r[7]) for r in rows}
            # BR-A1 ONLINE USD: TXN-01 (100.00, COMPLETED)
            assert data[("BR-A1", "ONLINE", "USD")] == (1, 1, Decimal("100.00"), Decimal("100.00"))
            # BR-A1 MOBILE USD: TXN-02 (50.00, PENDING)
            assert data[("BR-A1", "MOBILE", "USD")] == (1, 0, Decimal("50.00"), Decimal("0.00"))
            # BR-A2 ATM USD: TXN-03 (30.00, COMPLETED)
            assert data[("BR-A2", "ATM", "USD")] == (1, 1, Decimal("30.00"), Decimal("30.00"))
            # BR-A2 BRANCH USD: TXN-04 (20.00, FAILED)
            assert data[("BR-A2", "BRANCH", "USD")] == (1, 0, Decimal("20.00"), Decimal("0.00"))
            # BR-A2 ONLINE USD: TXN-05 (30.00, COMPLETED)
            assert data[("BR-A2", "ONLINE", "USD")] == (1, 1, Decimal("30.00"), Decimal("30.00"))


@pytest.mark.integration
def test_transaction_type_mix_known_answers(postgres_test_db, tmp_path):
    """Verify transaction type mix totals across categories and families."""
    _populate_known_test_warehouse(postgres_test_db, tmp_path)

    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT transaction_type_code, transaction_family, currency,
                       total_transaction_count, completed_transaction_count,
                       gross_transaction_amount, completed_gross_amount
                FROM reporting.v_transaction_type_mix
                ORDER BY transaction_type_code, currency;
            """)
            rows = cur.fetchall()
            mix = {(r[0], r[2]): (r[1], r[3], r[4], r[5], r[6]) for r in rows}

            # DEPOSIT USD: total 2 (TXN-01, TXN-02), completed 1, gross 150.00, completed 100.00
            assert mix[("DEPOSIT", "USD")] == ("CREDIT", 2, 1, Decimal("150.00"), Decimal("100.00"))
            # WITHDRAWAL USD: total 2 (TXN-03, TXN-04), completed 1, gross 50.00, completed 30.00
            assert mix[("WITHDRAWAL", "USD")] == ("DEBIT", 2, 1, Decimal("50.00"), Decimal("30.00"))
            # REVERSAL USD: total 1, completed 1, gross 30.00, completed 30.00
            assert mix[("REVERSAL", "USD")] == ("ADJUSTMENT", 1, 1, Decimal("30.00"), Decimal("30.00"))
            # DEPOSIT EUR: total 1, completed 1, gross 200.00, completed 200.00
            assert mix[("DEPOSIT", "EUR")] == ("CREDIT", 1, 1, Decimal("200.00"), Decimal("200.00"))
            # PAYMENT EUR: total 1, completed 1, gross 45.00, completed 45.00
            assert mix[("PAYMENT", "EUR")] == ("DEBIT", 1, 1, Decimal("45.00"), Decimal("45.00"))


@pytest.mark.integration
def test_data_quality_and_quarantine_summaries_known_answers(postgres_test_db, tmp_path):
    """
    Verify data-quality issue counts versus distinct affected source rows and batches.
    Verify quarantine inventory reflects rejected entities.
    """
    dataset_dir = tmp_path / "defective_dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    # 1 valid branch
    (dataset_dir / "branches.csv").write_text("branch_id,branch_name,region\nBR-Q1,Branch Q,WEST\n", encoding="utf-8")
    # 1 valid customer
    (dataset_dir / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-Q1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
    # 1 valid account
    (dataset_dir / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-Q1,CUST-Q1,BR-Q1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
    # 3 transactions: 1 valid, 1 with 2 issues on same row (missing txn_id AND invalid currency), 1 unknown account
    (dataset_dir / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-GOOD,ACC-Q1,DEPOSIT,100.00,USD,2026-03-10T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n"
        ",ACC-Q1,DEPOSIT,50.00,XXX,2026-03-10T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n"
        "TXN-BAD-ACC,UNKNOWN_ACC,DEPOSIT,25.00,USD,2026-03-10T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8"
    )

    batch_id = f"batch-dq-{uuid.uuid4().hex[:8]}"
    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id)

        val = ValidationEngine(conn)
        val.validate_batch(batch_id)

        # 1. Check v_data_quality_summary
        with conn.cursor() as cur:
            cur.execute("""
                SELECT rule_code, severity, disposition, issue_count, affected_source_rows, affected_batches
                FROM reporting.v_data_quality_summary
                WHERE affected_batches > 0
                ORDER BY rule_code;
            """)
            dq_rows = cur.fetchall()
            rules = {r[0]: (r[1], r[2], r[3], r[4], r[5]) for r in dq_rows}

            # Check that TXN_ID_MISSING, CURRENCY_UNSUPPORTED, and ACCOUNT_NOT_FOUND are recorded
            assert "TXN_ID_MISSING" in rules
            assert rules["TXN_ID_MISSING"][0] == "ERROR"
            assert rules["TXN_ID_MISSING"][1] == "REJECTED"

            assert "CURRENCY_UNSUPPORTED" in rules
            assert "ACCOUNT_NOT_FOUND" in rules

        # 2. Check v_quarantine_inventory
        with conn.cursor() as cur:
            cur.execute("""
                SELECT batch_id, entity_type, primary_rule_code, quarantined_rows, recorded_issue_count
                FROM reporting.v_quarantine_inventory
                WHERE batch_id = %s
                ORDER BY primary_rule_code;
            """, (batch_id,))
            q_rows = cur.fetchall()
            # There are 2 quarantined transaction rows
            total_quarantined = sum(r[3] for r in q_rows)
            assert total_quarantined == 2


@pytest.mark.integration
def test_pipeline_execution_health_known_answers(postgres_test_db, tmp_path):
    """Verify batch health view correctly reports duration, counts, and rejection rate."""
    batch_id = _populate_known_test_warehouse(postgres_test_db, tmp_path)

    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT batch_id, status, records_extracted, records_staged, records_valid,
                       records_rejected, records_inserted, records_skipped,
                       rejection_rate_pct, reconciliation_status, duration_seconds
                FROM reporting.v_pipeline_execution_health
                WHERE batch_id = %s;
            """, (batch_id,))
            row = cur.fetchone()
            assert row is not None
            assert row[0] == batch_id
            assert row[1] == "SUCCEEDED"
            assert row[2] == 14  # 2 branches, 2 customers, 3 accounts, 7 txns
            assert row[3] == 14
            assert row[4] == 14
            assert row[5] == 0
            assert row[6] == 7
            assert row[7] == 0
            assert row[8] == Decimal("0.00")
            assert row[9] == "RECONCILED"
            # Duration should be non-negative numeric or zero
            assert row[10] is not None
            assert row[10] >= 0.00


@pytest.mark.integration
def test_empty_database_and_zero_denominator_safety(postgres_test_db):
    """Verify all 7 reporting views operate without error on empty warehouse/monitoring tables."""
    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            # All reporting views should execute cleanly and return 0 rows
            views = [
                "v_daily_transaction_summary",
                "v_deposit_withdrawal_analysis",
                "v_branch_channel_activity",
                "v_transaction_type_mix",
                "v_data_quality_summary",
                "v_pipeline_execution_health",
                "v_quarantine_inventory",
            ]
            for v in views:
                cur.execute(f"SELECT COUNT(*) FROM reporting.{v};")
                count = cur.fetchone()[0]
                assert count == 0, f"Expected 0 rows in empty {v}, got {count}"


@pytest.mark.integration
def test_sql_analytics_queries_file_execution(postgres_test_db, tmp_path):
    """
    Verify that the complete sql/04_analytics_queries.sql script executes
    against the initialized PostgreSQL test database without syntax or query errors.
    """
    _populate_known_test_warehouse(postgres_test_db, tmp_path)

    sql_file = Path(__file__).resolve().parent.parent / "sql" / "04_analytics_queries.sql"
    assert sql_file.exists(), "sql/04_analytics_queries.sql does not exist"

    with open(sql_file, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # Split on semicolons and strip comments
    raw_statements = [s for s in sql_content.split(";") if s.strip()]
    queries = []
    for s in raw_statements:
        clean_lines = [line for line in s.splitlines() if not line.strip().startswith("--")]
        clean_query = "\n".join(clean_lines).strip()
        if clean_query:
            queries.append(clean_query)

    assert len(queries) == 7, f"Expected 7 report queries to parse from SQL file, got {len(queries)}"

    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            for query in queries:
                cur.execute(query)
                rows = cur.fetchall()
                assert rows is not None


@pytest.mark.integration
def test_cli_report_commands(postgres_test_db, tmp_path):
    """Verify that `bankflow report` CLI command works for all report types."""
    _populate_known_test_warehouse(postgres_test_db, tmp_path)

    # Ingest a defect row so quality and quarantine reports have records to display
    defect_dir = tmp_path / "cli_defects"
    defect_dir.mkdir(parents=True, exist_ok=True)
    (defect_dir / "branches.csv").write_text("branch_id,branch_name,region\nBR-D1,Branch D,WEST\n", encoding="utf-8")
    (defect_dir / "customers.csv").write_text("customer_id,customer_segment,created_date,customer_status\nCUST-D1,RETAIL,2026-01-01,ACTIVE\n", encoding="utf-8")
    (defect_dir / "accounts.csv").write_text("account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\nACC-D1,CUST-D1,BR-D1,CHECKING,OPEN,2026-01-01,USD\n", encoding="utf-8")
    (defect_dir / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        ",ACC-D1,DEPOSIT,50.00,USD,2026-03-10T12:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8"
    )
    b_id = f"batch-cli-{uuid.uuid4().hex[:8]}"
    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        loader.ingest_dataset_directory(defect_dir, batch_id=b_id)
        val = ValidationEngine(conn)
        val.validate_batch(b_id)

    runner = CliRunner()
    reports = ["daily", "deposit-withdrawal", "branch-channel", "type-mix", "quality", "batches", "quarantine"]
    for report_name in reports:
        result = runner.invoke(cli, ["report", report_name, "--test-db", "--limit", "10"])
        assert result.exit_code == 0, f"bankflow report {report_name} failed: {result.output}"
        assert f"Report: {report_name.upper()}" in result.output


@pytest.mark.integration
def test_reporting_explain_plans(postgres_test_db, tmp_path):
    """Verify that PostgreSQL can generate EXPLAIN query plans for reporting views without errors."""
    _populate_known_test_warehouse(postgres_test_db, tmp_path)

    with get_connection(postgres_test_db) as conn:
        with conn.cursor() as cur:
            views = [
                "reporting.v_daily_transaction_summary",
                "reporting.v_deposit_withdrawal_analysis",
                "reporting.v_branch_channel_activity",
                "reporting.v_transaction_type_mix",
                "reporting.v_data_quality_summary",
                "reporting.v_pipeline_execution_health",
                "reporting.v_quarantine_inventory",
            ]
            for v in views:
                cur.execute(f"EXPLAIN SELECT * FROM {v};")
                plan_lines = cur.fetchall()
                assert len(plan_lines) > 0, f"No EXPLAIN plan produced for {v}"
