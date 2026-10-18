"""
Unit tests for deployment scripts: smoke_test_deployment.py and bootstrap_remote_db.py.
"""

from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from scripts.smoke_test_deployment import SmokeTestRunner


def test_smoke_test_runner_initialization():
    runner = SmokeTestRunner(
        api_url="https://bankflow-api.onrender.com/",
        frontend_url="https://bankflow.vercel.app/",
        timeout=15,
    )
    assert runner.api_url == "https://bankflow-api.onrender.com"
    assert runner.frontend_url == "https://bankflow.vercel.app"
    assert runner.timeout == 15


@patch.object(SmokeTestRunner, "_http_request")
def test_smoke_test_runner_successful_run(mock_req):
    """Verify smoke test runner reports success when all endpoints return expected payloads."""
    # Route mock responses by endpoint
    def fake_request(url, method="GET", headers=None):
        if url.endswith("/"):
            return 200, {}, {"name": "BankFlow API", "version": "0.1.0"}
        elif url.endswith("/api/v1/health"):
            return 200, {}, {"status": "healthy", "database": "connected"}
        elif "/api/v1/overview" in url and method == "GET":
            return 200, {}, {"currencies": ["USD", "EUR"], "metrics_by_currency": [{"currency": "USD"}]}
        elif "/api/v1/daily" in url:
            return 200, {}, [{"reporting_date": "2026-03-01", "transaction_count": 10}]
        elif "/api/v1/deposit-withdrawal" in url:
            return 200, {}, [{"activity_group": "DEPOSIT", "transaction_count": 5}]
        elif "/api/v1/branch-channel" in url:
            return 200, {}, [{"branch_name": "Main", "channel": "ONLINE"}]
        elif "/api/v1/type-mix" in url:
            return 200, {}, [{"transaction_type": "DEPOSIT", "transaction_count": 5}]
        elif "/api/v1/quality" in url:
            return 200, {}, [{"rule_code": "TXN_ID_DUPLICATE", "issue_count": 2}]
        elif "/api/v1/batches" in url:
            return 200, {}, [{"batch_id": "b-1", "reconciliation_status": "RECONCILED"}]
        elif "/api/v1/transactions" in url:
            return 200, {}, {"items": [{"transaction_id": "tx-1"}], "total": 1}
        elif "/api/v1/overview" in url and method == "OPTIONS":
            return 200, {"access-control-allow-origin": "https://bankflow.vercel.app"}, {}
        elif "/api/v1/overview" in url and method == "POST":
            return 405, {}, {"detail": "Method Not Allowed"}
        elif url == "https://bankflow.vercel.app":
            return 200, {}, "<!DOCTYPE html><html><body>BankFlow Dashboard</body></html>"
        return 404, {}, {"detail": "Not Found"}

    mock_req.side_effect = fake_request

    runner = SmokeTestRunner(
        api_url="https://bankflow-api.onrender.com",
        frontend_url="https://bankflow.vercel.app",
        timeout=5,
    )
    success = runner.run_all()
    assert success is True
    assert len(runner.results) == 13
    assert all(passed for _, passed, _ in runner.results)


@patch.object(SmokeTestRunner, "_http_request")
def test_smoke_test_runner_detects_unhealthy_database(mock_req):
    """Verify smoke test runner reports failure when database is disconnected."""
    def fake_request(url, method="GET", headers=None):
        if url.endswith("/api/v1/health"):
            return 503, {}, {"status": "unhealthy", "database": "disconnected"}
        return 200, {}, {}

    mock_req.side_effect = fake_request

    runner = SmokeTestRunner(api_url="https://bankflow-api.onrender.com")
    success = runner.run_all()
    assert success is False

    health_result = next((r for r in runner.results if "Health & Database" in r[0]), None)
    assert health_result is not None
    assert health_result[1] is False


def test_smoke_test_runner_default_timeout():
    """Verify smoke test runner defaults to 90 seconds to tolerate Render cold starts."""
    runner = SmokeTestRunner(api_url="https://bankflow-api.onrender.com")
    assert runner.timeout == 90


@patch("urllib.request.urlopen")
def test_smoke_test_runner_handles_timeout_error(mock_urlopen):
    """Verify smoke test handles timeout cleanly without leaking credentials."""
    import socket
    mock_urlopen.side_effect = socket.timeout("timed out")
    runner = SmokeTestRunner(api_url="https://bankflow-api.onrender.com", timeout=90)
    with pytest.raises(RuntimeError) as exc_info:
        runner._http_request("https://bankflow-api.onrender.com/api/v1/health")
    err_msg = str(exc_info.value)
    assert "Request timed out after 90s to https://bankflow-api.onrender.com/api/v1/health (possible cold-start spin-up in progress)." in err_msg
    # Ensure no credentials leaked in error message
    assert "password" not in err_msg.lower()
    assert "token" not in err_msg.lower()


from bankflow.config import DatabaseConfig, get_settings
from scripts.bootstrap_remote_db import (
    BootstrapPreflightError,
    bootstrap_database,
    validate_bootstrap_target,
)


def test_bootstrap_rejects_accidental_local_target_without_allow_local():
    """Verify bootstrap rejects local host targets when --allow-local is not provided."""
    cfg = DatabaseConfig(host="127.0.0.1", port=5432, name="bankflow", user="postgres")
    with pytest.raises(BootstrapPreflightError) as exc_info:
        validate_bootstrap_target(cfg, confirm_target="127.0.0.1", allow_local=False)
    assert "Accidental local target rejected" in str(exc_info.value)
    assert "Pass --allow-local" in str(exc_info.value)

    # Also test 'localhost'
    cfg_localhost = DatabaseConfig(host="localhost", port=5432, name="bankflow", user="postgres")
    with pytest.raises(BootstrapPreflightError) as exc_info:
        validate_bootstrap_target(cfg_localhost, confirm_target="localhost", allow_local=False)
    assert "Accidental local target rejected" in str(exc_info.value)


def test_bootstrap_permits_local_target_with_allow_local():
    """Verify bootstrap allows local host when --allow-local is True."""
    cfg = DatabaseConfig(host="127.0.0.1", port=5432, name="bankflow", user="postgres")
    # Succeeds without raising when confirm_target matches
    validate_bootstrap_target(cfg, confirm_target="127.0.0.1", allow_local=True)


def test_bootstrap_rejects_missing_or_blank_confirm_target():
    """Verify bootstrap requires explicit confirm_target."""
    cfg = DatabaseConfig(host="ep-cool-fog.neon.tech", port=5432, name="neondb", user="alex", sslmode="require")
    with pytest.raises(BootstrapPreflightError) as exc_info:
        validate_bootstrap_target(cfg, confirm_target=None)
    assert "Explicit target confirmation required" in str(exc_info.value)

    with pytest.raises(BootstrapPreflightError) as exc_info:
        validate_bootstrap_target(cfg, confirm_target="   ")
    assert "Explicit target confirmation required" in str(exc_info.value)


def test_bootstrap_rejects_mismatched_confirm_target():
    """Verify bootstrap rejects mismatched confirm_target."""
    cfg = DatabaseConfig(host="ep-cool-fog.neon.tech", port=5432, name="neondb", user="alex", sslmode="require")
    with pytest.raises(BootstrapPreflightError) as exc_info:
        validate_bootstrap_target(cfg, confirm_target="ep-other-fog.neon.tech")
    assert "Target confirmation mismatch" in str(exc_info.value)
    assert "does not match resolved target host 'ep-cool-fog.neon.tech'" in str(exc_info.value)


def test_bootstrap_accepts_valid_confirm_target_variations():
    """Verify bootstrap accepts host, host:port, or host/dbname variations."""
    cfg = DatabaseConfig(host="ep-cool-fog.neon.tech", port=5432, name="neondb", user="alex", sslmode="require")
    validate_bootstrap_target(cfg, confirm_target="ep-cool-fog.neon.tech")
    validate_bootstrap_target(cfg, confirm_target="ep-cool-fog.neon.tech:5432")
    validate_bootstrap_target(cfg, confirm_target="ep-cool-fog.neon.tech/neondb")
    validate_bootstrap_target(cfg, confirm_target="ep-cool-fog.neon.tech:5432/neondb")


def test_bootstrap_rejects_remote_target_without_ssl():
    """Verify hosted PostgreSQL target requires TLS unless require_ssl=False."""
    cfg = DatabaseConfig(host="ep-cool-fog.neon.tech", port=5432, name="neondb", user="alex", sslmode=None)
    with pytest.raises(BootstrapPreflightError) as exc_info:
        validate_bootstrap_target(cfg, confirm_target="ep-cool-fog.neon.tech", require_ssl=True)
    assert "Insecure remote target rejected" in str(exc_info.value)
    assert "lacks required TLS/SSL configuration" in str(exc_info.value)

    # Allows when require_ssl=False
    validate_bootstrap_target(cfg, confirm_target="ep-cool-fog.neon.tech", require_ssl=False)


def test_bootstrap_preflight_fails_before_connection_or_ddl(monkeypatch):
    """Verify that a preflight error halts execution before attempting database connection or schema DDL."""
    monkeypatch.setenv("BANKFLOW_DB_HOST", "ep-cool-fog.neon.tech")
    monkeypatch.setenv("BANKFLOW_DB_SSLMODE", "require")

    with patch("scripts.bootstrap_remote_db.get_connection") as mock_conn:
        with pytest.raises(BootstrapPreflightError):
            # Calling bootstrap_database with no confirm_target must fail preflight
            bootstrap_database(confirm_target=None)
        # Verify get_connection was never called
        mock_conn.assert_not_called()


def test_bootstrap_configuration_precedence_database_url(monkeypatch):
    """Verify DATABASE_URL takes precedence in resolving target database host and sslmode."""
    remote_url = "postgresql://alex:secret@ep-cool-fog.neon.tech:5432/remote_db?sslmode=require"
    monkeypatch.setenv("DATABASE_URL", remote_url)
    monkeypatch.setenv("BANKFLOW_DB_HOST", "127.0.0.1")

    settings = get_settings()
    assert settings.db.host == "ep-cool-fog.neon.tech"
    assert settings.db.name == "remote_db"
    assert settings.db.sslmode == "require"

    # Preflight validation validates against the resolved DATABASE_URL host
    validate_bootstrap_target(settings.db, confirm_target="ep-cool-fog.neon.tech")


def test_bootstrap_preserves_reporting_password_byte_for_byte(monkeypatch):
    """Verify reporting password with leading/trailing spaces is preserved byte-for-byte in SQL statement."""
    settings = get_settings()
    target_host = settings.db.host

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    exact_pw = "  exact_secret_password_with_spaces  "

    with patch("scripts.bootstrap_remote_db.get_connection", return_value=mock_conn):
        with patch("scripts.bootstrap_remote_db.init_staging_schema"), \
             patch("scripts.bootstrap_remote_db.init_validation_schema"), \
             patch("scripts.bootstrap_remote_db.init_warehouse_schema"), \
             patch("scripts.bootstrap_remote_db.init_reporting_schema"):
            bootstrap_database(
                reporting_password=exact_pw,
                skip_data_load=True,
                confirm_target=target_host,
                allow_local=True,
            )

    # Check the ALTER ROLE call on cursor
    alter_calls = [c for c in mock_cursor.execute.call_args_list if "WITH PASSWORD" in str(c)]
    assert len(alter_calls) == 1
    args, _ = alter_calls[0]
    assert args[0] == "ALTER ROLE bankflow_reporting_user WITH PASSWORD %s;"
    # Password argument must be exact, not stripped
    assert args[1] == (exact_pw,)
