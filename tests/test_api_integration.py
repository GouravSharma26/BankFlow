"""
PostgreSQL integration tests for BankFlow Phase 5:
Read-only reporting API endpoints, security controls, parameter validation,
and equality against conformed reporting views.
"""

from __future__ import annotations

import os
import uuid
from decimal import Decimal
from pathlib import Path

import pytest
import psycopg2
from fastapi.testclient import TestClient

from bankflow.analytics.schema import init_reporting_schema
from bankflow.api.app import create_app
from bankflow.api.db import readonly_db_session
from bankflow.config import DatabaseConfig, get_settings
from bankflow.db import check_connection, get_connection
from bankflow.generator.defects import DefectConfig
from bankflow.generator.generator import SyntheticDataGenerator
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
        init_reporting_schema(conn, force=True)

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


@pytest.fixture
def api_client(postgres_test_db):
    """FastAPI TestClient bound to the isolated PostgreSQL test database."""
    app = create_app(db_config=postgres_test_db, use_test_db=True)
    return TestClient(app)


def _populate_known_test_warehouse(postgres_test_db, tmp_path: Path) -> str:
    """Helper to populate deterministic records across two dates and currencies."""
    dataset_dir = tmp_path / f"api_test_data_{uuid.uuid4().hex[:6]}"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    (dataset_dir / "branches.csv").write_text(
        "branch_id,branch_name,region\n"
        "BR-A1,Branch Alpha,NORTH\n"
        "BR-A2,Branch Beta,SOUTH\n",
        encoding="utf-8"
    )

    (dataset_dir / "customers.csv").write_text(
        "customer_id,customer_segment,created_date,customer_status\n"
        "CUST-A1,RETAIL,2026-01-01,ACTIVE\n"
        "CUST-A2,PREMIUM,2026-01-15,ACTIVE\n",
        encoding="utf-8"
    )

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

    batch_id = f"batch-api-{uuid.uuid4().hex[:8]}"
    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id)

        val = ValidationEngine(conn)
        val.validate_batch(batch_id)

        wh = WarehouseLoader(conn)
        wh.load_batch(batch_id)

    return batch_id


@pytest.mark.integration
def test_api_health_endpoint(api_client):
    """Verify GET /api/v1/health returns 200 with service status and database connectivity."""
    resp = api_client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "bankflow-reporting-api"
    assert data["database"] == "connected"
    assert "password" not in resp.text.lower()


@pytest.mark.integration
def test_api_health_database_failure():
    """Verify health endpoint returns 503 without leaking credentials if database is unavailable."""
    bad_config = DatabaseConfig(
        host="127.0.0.1",
        port=54399,  # Unused port
        name="bankflow_test",
        user="postgres",
        password="secret_password",
    )

    bad_app = create_app(db_config=bad_config, use_test_db=True)
    bad_client = TestClient(bad_app)

    resp = bad_client.get("/api/v1/health")
    assert resp.status_code == 503
    data = resp.json()
    assert data["status"] == "degraded"
    assert data["database"] == "unavailable"
    assert "secret_password" not in resp.text


@pytest.mark.integration
def test_api_root_info(api_client):
    """Verify root endpoint returns API metadata and documentation path."""
    resp = api_client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "BankFlow Reporting API"
    assert data["documentation"] == "/docs"


@pytest.mark.integration
def test_api_cors_headers(api_client):
    """Verify CORS headers are returned for configured frontend origin."""
    resp = api_client.options(
        "/api/v1/overview",
        headers={
            "Origin": "https://bankflow-analytics-console.lovable.app",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "https://bankflow-analytics-console.lovable.app"


@pytest.mark.integration
def test_api_read_only_enforcement(postgres_test_db):
    """Verify that database sessions created by the API strictly forbid data mutations."""
    with pytest.raises(psycopg2.errors.ReadOnlySqlTransaction):
        with readonly_db_session(postgres_test_db) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO staging.stg_branches (branch_id, branch_name, region) VALUES ('B', 'B', 'R');")


@pytest.mark.integration
def test_api_endpoints_empty_database(api_client):
    """Verify all reporting endpoints return clean empty responses without crashing on zero division."""
    resp_overview = api_client.get("/api/v1/overview")
    assert resp_overview.status_code == 200
    data_ov = resp_overview.json()
    assert data_ov["currencies"] == []
    assert data_ov["total_batches"] == 0

    endpoints = [
        "/api/v1/daily",
        "/api/v1/deposit-withdrawal",
        "/api/v1/branch-channel",
        "/api/v1/type-mix",
        "/api/v1/quality",
        "/api/v1/batches",
        "/api/v1/quarantine",
    ]
    for ep in endpoints:
        resp = api_client.get(ep)
        assert resp.status_code == 200, f"Endpoint {ep} failed on empty database"
        assert resp.json() == []

    resp_txns = api_client.get("/api/v1/transactions")
    assert resp_txns.status_code == 200
    assert resp_txns.json()["total"] == 0
    assert resp_txns.json()["items"] == []


@pytest.mark.integration
def test_api_overview_matches_views(api_client, postgres_test_db, tmp_path):
    """Verify GET /api/v1/overview returns accurate metrics matching known loaded batch."""
    _populate_known_test_warehouse(postgres_test_db, tmp_path)

    resp = api_client.get("/api/v1/overview")
    assert resp.status_code == 200
    data = resp.json()

    assert data["currencies"] == ["EUR", "USD"]
    assert data["earliest_date"] == "2026-03-15"
    assert data["latest_date"] == "2026-03-16"
    assert data["total_batches"] == 1
    assert data["latest_batch_status"] == "SUCCEEDED"

    # EUR summary: 2 txns, 2 completed, gross 245.00
    eur_metric = next(m for m in data["metrics_by_currency"] if m["currency"] == "EUR")
    assert eur_metric["total_transactions"] == 2
    assert eur_metric["completed_transactions"] == 2
    assert eur_metric["gross_transaction_amount"] == "245.00"
    assert eur_metric["completed_gross_amount"] == "245.00"
    assert eur_metric["acceptance_rate_pct"] == "100.00"
    assert eur_metric["active_accounts"] == 1
    assert eur_metric["active_customers"] == 1

    # USD summary: 5 txns, 3 completed, gross 230.00, completed 160.00 (100 + 30 + 30)
    usd_metric = next(m for m in data["metrics_by_currency"] if m["currency"] == "USD")
    assert usd_metric["total_transactions"] == 5
    assert usd_metric["completed_transactions"] == 3
    assert usd_metric["gross_transaction_amount"] == "230.00"
    assert usd_metric["completed_gross_amount"] == "160.00"
    assert usd_metric["acceptance_rate_pct"] == "60.00"
    assert usd_metric["active_accounts"] == 2
    assert usd_metric["active_customers"] == 2


@pytest.mark.integration
def test_api_daily_filtering_and_equality(api_client, postgres_test_db, tmp_path):
    """Verify GET /api/v1/daily handles filtering and matches direct SQL view outputs."""
    _populate_known_test_warehouse(postgres_test_db, tmp_path)

    # 1. Query all
    resp_all = api_client.get("/api/v1/daily")
    assert resp_all.status_code == 200
    rows = resp_all.json()
    assert len(rows) == 2  # 1 for USD (2026-03-15), 1 for EUR (2026-03-16)

    # 2. Filter currency
    resp_usd = api_client.get("/api/v1/daily?currency=USD")
    assert resp_usd.status_code == 200
    usd_rows = resp_usd.json()
    assert len(usd_rows) == 1
    assert usd_rows[0]["currency"] == "USD"
    assert usd_rows[0]["reporting_date"] == "2026-03-15"
    assert usd_rows[0]["total_transaction_count"] == 5
    assert usd_rows[0]["gross_transaction_amount"] == "230.00"

    # 3. Filter date range
    resp_date = api_client.get("/api/v1/daily?start_date=2026-03-16&end_date=2026-03-16")
    assert resp_date.status_code == 200
    date_rows = resp_date.json()
    assert len(date_rows) == 1
    assert date_rows[0]["currency"] == "EUR"

    # 4. Bad request validations
    bad_curr = api_client.get("/api/v1/daily?currency=INVALID")
    assert bad_curr.status_code == 400

    bad_date = api_client.get("/api/v1/daily?start_date=2026-03-20&end_date=2026-03-10")
    assert bad_date.status_code == 400


@pytest.mark.integration
def test_api_deposit_withdrawal_shares(api_client, postgres_test_db, tmp_path):
    """Verify deposit versus withdrawal shares are calculated accurately."""
    _populate_known_test_warehouse(postgres_test_db, tmp_path)

    resp = api_client.get("/api/v1/deposit-withdrawal?currency=USD")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    r = rows[0]
    # Completed deposits: 100.00, completed withdrawals: 30.00. Total completed = 130.00
    assert r["completed_deposit_count"] == 1
    assert r["completed_deposit_gross_amount"] == "100.00"
    assert r["completed_withdrawal_count"] == 1
    assert r["completed_withdrawal_gross_amount"] == "30.00"
    assert r["deposit_value_share_pct"] == "76.92"
    assert r["withdrawal_value_share_pct"] == "23.08"


@pytest.mark.integration
def test_api_branch_channel_and_type_mix(api_client, postgres_test_db, tmp_path):
    """Verify branch/channel filtering and type mix distribution metrics."""
    _populate_known_test_warehouse(postgres_test_db, tmp_path)

    # Branch channel
    resp_bc = api_client.get("/api/v1/branch-channel?channel=ONLINE")
    assert resp_bc.status_code == 200
    bc_rows = resp_bc.json()
    assert len(bc_rows) >= 1
    assert all(row["channel"] == "ONLINE" for row in bc_rows)

    bad_channel = api_client.get("/api/v1/branch-channel?channel=TELEPORT")
    assert bad_channel.status_code == 400

    # Type mix
    resp_tm = api_client.get("/api/v1/type-mix?currency=USD")
    assert resp_tm.status_code == 200
    tm_rows = resp_tm.json()
    assert len(tm_rows) >= 3  # DEPOSIT, WITHDRAWAL, REVERSAL
    # Total percentage shares should sum close to 100%
    event_share_sum = sum(float(row["event_share_pct"]) for row in tm_rows)
    assert abs(event_share_sum - 100.0) < 0.1


@pytest.mark.integration
def test_api_quality_batches_quarantine(api_client, postgres_test_db, tmp_path):
    """Verify quality, batch execution, and quarantine endpoints on defective dataset."""
    dataset_dir = tmp_path / "defective_dataset"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    generator = SyntheticDataGenerator(seed=42, defect_config=DefectConfig.standard_test_defects())
    generator.export_all(
        output_dir=dataset_dir,
        num_branches=2,
        num_customers=5,
        num_accounts=10,
        num_transactions=30,
    )



    batch_id = f"batch-defects-{uuid.uuid4().hex[:6]}"
    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id)

        val = ValidationEngine(conn)
        val.validate_batch(batch_id)

    # Quality endpoint
    resp_q = api_client.get("/api/v1/quality")
    assert resp_q.status_code == 200
    q_rows = resp_q.json()
    assert len(q_rows) > 0
    assert any(row["severity"] == "ERROR" for row in q_rows)

    bad_sev = api_client.get("/api/v1/quality?severity=CATASTROPHIC")
    assert bad_sev.status_code == 400

    # Batches endpoint
    resp_b = api_client.get("/api/v1/batches")
    assert resp_b.status_code == 200
    b_rows = resp_b.json()
    assert len(b_rows) >= 1
    assert any(b["batch_id"] == batch_id for b in b_rows)

    # Quarantine endpoint
    resp_quar = api_client.get("/api/v1/quarantine")
    assert resp_quar.status_code == 200
    quar_rows = resp_quar.json()
    assert len(quar_rows) > 0


@pytest.mark.integration
def test_api_transactions_pagination_and_sorting(api_client, postgres_test_db, tmp_path):
    """Verify transactions endpoint pagination, sorting, and field whitelist."""
    _populate_known_test_warehouse(postgres_test_db, tmp_path)

    # 1. Page 1, page_size 3, sorted by amount desc
    resp_p1 = api_client.get("/api/v1/transactions?page=1&page_size=3&sort_by=amount&sort_order=desc")
    assert resp_p1.status_code == 200
    data_p1 = resp_p1.json()
    assert data_p1["total"] == 7
    assert data_p1["total_pages"] == 3
    assert len(data_p1["items"]) == 3
    # Top amounts: 200.00, 100.00, 50.00
    assert data_p1["items"][0]["amount"] == "200.00"
    assert data_p1["items"][1]["amount"] == "100.00"
    assert data_p1["items"][2]["amount"] == "50.00"

    # 2. Page 2
    resp_p2 = api_client.get("/api/v1/transactions?page=2&page_size=3&sort_by=amount&sort_order=desc")
    assert resp_p2.status_code == 200
    data_p2 = resp_p2.json()
    assert len(data_p2["items"]) == 3
    assert data_p2["items"][0]["amount"] == "45.00"

    # 3. Filter by status
    resp_failed = api_client.get("/api/v1/transactions?status=FAILED")
    assert resp_failed.status_code == 200
    failed_data = resp_failed.json()
    assert failed_data["total"] == 1
    assert failed_data["items"][0]["transaction_id"] == "TXN-04"
    assert failed_data["items"][0]["status"] == "FAILED"

    # 4. Bad request validations
    assert api_client.get("/api/v1/transactions?sort_by=secret").status_code == 400
    assert api_client.get("/api/v1/transactions?sort_order=sideways").status_code == 400
    assert api_client.get("/api/v1/transactions?status=NOT_A_STATUS").status_code == 400


@pytest.mark.integration
def test_api_overview_multiday_overlapping_entities(api_client, postgres_test_db, tmp_path):
    """
    Regression fixture for Finding 4:
    Multi-day, same-currency dataset with overlapping accounts and customers across days.
    Day 1 has 2 accounts, 2 customers.
    Day 2 has 2 accounts (1 overlapping, 1 new), 2 customers (1 overlapping, 1 new).
    Day 3 has 1 account (overlapping), 1 customer (overlapping).
    Single-day MAX would incorrectly return 2.
    Simple SUM would incorrectly return 5.
    Period-wide distinct count must accurately return 3 accounts and 3 customers.
    """
    dataset_dir = tmp_path / f"multiday_test_data_{uuid.uuid4().hex[:6]}"
    dataset_dir.mkdir(parents=True, exist_ok=True)

    (dataset_dir / "branches.csv").write_text(
        "branch_id,branch_name,region\n"
        "BR-01,Central,NORTH\n",
        encoding="utf-8",
    )

    (dataset_dir / "customers.csv").write_text(
        "customer_id,customer_segment,created_date,customer_status\n"
        "CUST-01,RETAIL,2026-01-01,ACTIVE\n"
        "CUST-02,PREMIUM,2026-01-02,ACTIVE\n"
        "CUST-03,SMALL_BUSINESS,2026-01-03,ACTIVE\n",
        encoding="utf-8",
    )

    (dataset_dir / "accounts.csv").write_text(
        "account_id,customer_id,branch_id,account_type,account_status,opened_date,currency\n"
        "ACC-01,CUST-01,BR-01,CHECKING,OPEN,2026-01-01,USD\n"
        "ACC-02,CUST-02,BR-01,SAVINGS,OPEN,2026-01-02,USD\n"
        "ACC-03,CUST-03,BR-01,CHECKING,OPEN,2026-01-03,USD\n",
        encoding="utf-8",
    )

    # 5 transactions across 3 consecutive days for USD:
    # Day 1 (2026-03-10): ACC-01 (CUST-01), ACC-02 (CUST-02) -> 2 accts, 2 custs
    # Day 2 (2026-03-11): ACC-02 (CUST-02), ACC-03 (CUST-03) -> 2 accts, 2 custs (ACC-02/CUST-02 overlaps)
    # Day 3 (2026-03-12): ACC-01 (CUST-01)                    -> 1 acct,  1 cust  (ACC-01/CUST-01 overlaps)
    (dataset_dir / "transactions.csv").write_text(
        "transaction_id,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-MD-01,ACC-01,DEPOSIT,100.00,USD,2026-03-10T10:00:00+00:00,COMPLETED,ONLINE,,CORE\n"
        "TXN-MD-02,ACC-02,DEPOSIT,200.00,USD,2026-03-10T11:00:00+00:00,COMPLETED,BRANCH,,CORE\n"
        "TXN-MD-03,ACC-02,WITHDRAWAL,50.00,USD,2026-03-11T09:00:00+00:00,COMPLETED,ATM,,CORE\n"
        "TXN-MD-04,ACC-03,PAYMENT,75.00,USD,2026-03-11T14:00:00+00:00,COMPLETED,MOBILE,,CORE\n"
        "TXN-MD-05,ACC-01,DEPOSIT,120.00,USD,2026-03-12T16:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8",
    )

    batch_id = f"batch-multiday-{uuid.uuid4().hex[:8]}"
    with get_connection(postgres_test_db) as conn:
        loader = StagingLoader(conn)
        loader.ingest_dataset_directory(dataset_dir, batch_id=batch_id)
        val = ValidationEngine(conn)
        val.validate_batch(batch_id)
        wh = WarehouseLoader(conn)
        wh.load_batch(batch_id)

    # 1. Verify period-wide overview without filter
    resp = api_client.get("/api/v1/overview")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["metrics_by_currency"]) == 1
    usd_metric = data["metrics_by_currency"][0]
    assert usd_metric["currency"] == "USD"
    assert usd_metric["total_transactions"] == 5
    assert usd_metric["completed_transactions"] == 5
    assert usd_metric["gross_transaction_amount"] == "545.00"
    # CRITICAL: Max single-day is 2, Sum of daily is 5. Period-wide distinct count must be 3!
    assert usd_metric["active_accounts"] == 3
    assert usd_metric["active_customers"] == 3

    # 2. Verify period-wide overview with currency filter
    resp_usd = api_client.get("/api/v1/overview?currency=USD")
    assert resp_usd.status_code == 200
    data_usd = resp_usd.json()
    assert len(data_usd["metrics_by_currency"]) == 1
    assert data_usd["metrics_by_currency"][0]["active_accounts"] == 3
    assert data_usd["metrics_by_currency"][0]["active_customers"] == 3


@pytest.mark.integration
@pytest.mark.parametrize(
    "invalid_date",
    [
        "20260315",       # Compact date
        "2026-W11-7",     # ISO week date
        "2026-02-29",     # Invalid calendar date (not a leap year)
        "2026-04-31",     # Invalid calendar date (April has 30 days)
        "2026-13-01",     # Invalid month
        "malformed",      # Non-date string
        "2026/03/15",     # Slash delimiter
        " 2026-03-15 ",   # Trailing/leading whitespace
        "",               # Empty string
    ],
)
def test_api_strict_date_validation_rejected(api_client, invalid_date):
    """Verify exact YYYY-MM-DD parsing rejects compact, week, malformed, and invalid calendar dates."""
    resp_start = api_client.get(f"/api/v1/daily?start_date={invalid_date}")
    assert resp_start.status_code == 400
    assert "Invalid start_date" in resp_start.json()["detail"]

    resp_end = api_client.get(f"/api/v1/daily?end_date={invalid_date}")
    assert resp_end.status_code == 400
    assert "Invalid end_date" in resp_end.json()["detail"]


@pytest.mark.integration
def test_api_currency_validation(api_client):
    """Verify supported currencies (USD, EUR, GBP) are accepted and others rejected with 400."""
    for curr in ["USD", "EUR", "GBP", "usd", "eur", "gbp"]:
        resp = api_client.get(f"/api/v1/overview?currency={curr}")
        assert resp.status_code == 200, f"Supported currency '{curr}' failed"

    for bad_curr in ["CAD", "JPY", "XYZ", "INVALID", "123"]:
        resp = api_client.get(f"/api/v1/overview?currency={bad_curr}")
        assert resp.status_code == 400, f"Unsupported currency '{bad_curr}' did not return 400"
        assert "Supported currencies" in resp.json()["detail"]


@pytest.mark.integration
def test_api_quality_disposition_validation(api_client):
    """Verify canonical dispositions (ACCEPTED, REJECTED, WARNED, SKIPPED) pass and others return 400."""
    for disp in ["ACCEPTED", "REJECTED", "WARNED", "SKIPPED", "accepted", "rejected", "warned", "skipped"]:
        resp = api_client.get(f"/api/v1/quality?disposition={disp}")
        assert resp.status_code == 200, f"Canonical disposition '{disp}' failed"

    for bad_disp in ["LOGGED", "QUARANTINED", "UNKNOWN", "DROP", "123"]:
        resp = api_client.get(f"/api/v1/quality?disposition={bad_disp}")
        assert resp.status_code == 400, f"Invalid disposition '{bad_disp}' did not return 400"
        assert "Permitted values" in resp.json()["detail"]
