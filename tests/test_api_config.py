"""
Unit and regression tests for BankFlow Reporting API configuration precedence.
Verifies ApiConfig resolution, environment variable overrides, CLI precedence,
and dedicated reporting user/password handling.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from bankflow.__main__ import cli
from bankflow.api.config import ApiConfig
from bankflow.config import get_settings


def test_api_config_defaults(monkeypatch):
    """Verify default ApiConfig values when no overrides are set."""
    monkeypatch.delenv("BANKFLOW_API_HOST", raising=False)
    monkeypatch.delenv("BANKFLOW_API_PORT", raising=False)
    monkeypatch.delenv("BANKFLOW_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("BANKFLOW_REPORTING_DB_USER", raising=False)
    monkeypatch.delenv("BANKFLOW_REPORTING_DB_PASSWORD", raising=False)

    config = ApiConfig.from_env(use_test_db=False)
    settings = get_settings()

    assert config.host == "127.0.0.1"
    assert config.port == 8000
    assert config.db_config.host == settings.db.host
    assert config.db_config.port == settings.db.port
    assert config.db_config.name == settings.db.name
    assert config.db_config.user == settings.db.user
    assert "https://bankflow-analytics-console.lovable.app" in config.cors_origins


def test_api_config_test_database_resolution(monkeypatch):
    """Verify use_test_db=True targets test database config."""
    monkeypatch.delenv("BANKFLOW_REPORTING_DB_USER", raising=False)
    monkeypatch.delenv("BANKFLOW_REPORTING_DB_PASSWORD", raising=False)

    config = ApiConfig.from_env(use_test_db=True)
    settings = get_settings()

    assert config.db_config.name == settings.test_db.name
    assert config.db_config.user == settings.test_db.user


def test_api_config_reporting_credentials_override(monkeypatch):
    """Verify BANKFLOW_REPORTING_DB_USER and PASSWORD override default DB credentials."""
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_USER", "custom_reporting_role")
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_PASSWORD", "custom_reporting_pass_123")

    config = ApiConfig.from_env(use_test_db=False)
    settings = get_settings()

    assert config.db_config.user == "custom_reporting_role"
    assert config.db_config.password == "custom_reporting_pass_123"
    assert config.db_config.name == settings.db.name

    # Check test db with reporting credentials
    test_config = ApiConfig.from_env(use_test_db=True)
    assert test_config.db_config.user == "custom_reporting_role"
    assert test_config.db_config.password == "custom_reporting_pass_123"
    assert test_config.db_config.name == settings.test_db.name


def test_api_config_cli_overrides_env_precedence(monkeypatch):
    """Verify explicit CLI arguments take precedence over environment variables."""
    monkeypatch.setenv("BANKFLOW_API_HOST", "192.168.1.10")
    monkeypatch.setenv("BANKFLOW_API_PORT", "7000")

    # Env variables apply when explicit arguments are None
    env_config = ApiConfig.from_env()
    assert env_config.host == "192.168.1.10"
    assert env_config.port == 7000

    # Explicit arguments override environment variables
    cli_config = ApiConfig.from_env(host="0.0.0.0", port=9000)
    assert cli_config.host == "0.0.0.0"
    assert cli_config.port == 9000


def test_api_config_cors_origins_parsing(monkeypatch):
    """Verify comma-separated BANKFLOW_CORS_ORIGINS is parsed cleanly."""
    monkeypatch.setenv("BANKFLOW_CORS_ORIGINS", "https://console.example.com, http://localhost:8080 ")

    config = ApiConfig.from_env()
    assert config.cors_origins == ("https://console.example.com", "http://localhost:8080")


@patch("uvicorn.run")
def test_bankflow_serve_cli_uses_resolved_config(mock_uvicorn_run, monkeypatch):
    """Regression test: verify 'bankflow serve' uses resolved ApiConfig with reporting role."""
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_USER", "bankflow_reporting_user")
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_PASSWORD", "secure_test_password")
    monkeypatch.setenv("BANKFLOW_API_HOST", "127.0.0.1")
    monkeypatch.setenv("BANKFLOW_API_PORT", "8888")

    runner = CliRunner()
    result = runner.invoke(cli, ["serve", "--port", "8888", "--test-db"])

    assert result.exit_code == 0
    assert "Starting BankFlow Read-Only Reporting API on http://127.0.0.1:8888..." in result.output
    assert "as user 'bankflow_reporting_user'" in result.output
    assert mock_uvicorn_run.called
    call_args = mock_uvicorn_run.call_args
    assert call_args.kwargs["host"] == "127.0.0.1"
    assert call_args.kwargs["port"] == 8888
