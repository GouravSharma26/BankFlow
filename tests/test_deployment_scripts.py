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
