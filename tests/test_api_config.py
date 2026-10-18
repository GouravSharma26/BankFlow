"""
Unit and regression tests for BankFlow Reporting API configuration precedence.
Verifies ApiConfig resolution, environment variable overrides, CLI precedence,
and paired dedicated reporting user/password handling.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from bankflow.__main__ import cli
from bankflow.api.config import ApiConfig, ApiConfigurationError
from bankflow.config import get_settings


@pytest.fixture(autouse=True)
def clean_reporting_env(monkeypatch):
    """Ensure environment is strictly isolated and reporting credentials are reset."""
    monkeypatch.delenv("BANKFLOW_REPORTING_DB_USER", raising=False)
    monkeypatch.delenv("BANKFLOW_REPORTING_DB_PASSWORD", raising=False)
    monkeypatch.delenv("BANKFLOW_API_HOST", raising=False)
    monkeypatch.delenv("BANKFLOW_API_PORT", raising=False)
    monkeypatch.delenv("BANKFLOW_CORS_ORIGINS", raising=False)


def test_api_config_defaults():
    """Verify default ApiConfig values when no overrides are set."""
    config = ApiConfig.from_env(use_test_db=False)
    settings = get_settings()

    assert config.host == "127.0.0.1"
    assert config.port == 8000
    assert config.db_config.host == settings.db.host
    assert config.db_config.port == settings.db.port
    assert config.db_config.name == settings.db.name
    assert config.db_config.user == settings.db.user
    assert config.db_config.password == settings.db.password
    assert "https://bankflow-analytics-console.lovable.app" in config.cors_origins


def test_api_config_test_database_resolution():
    """Verify use_test_db=True targets test database config."""
    config = ApiConfig.from_env(use_test_db=True)
    settings = get_settings()

    assert config.db_config.name == settings.test_db.name
    assert config.db_config.user == settings.test_db.user
    assert config.db_config.password == settings.test_db.password


def test_api_config_reporting_credentials_paired_override(monkeypatch):
    """Verify BANKFLOW_REPORTING_DB_USER and PASSWORD override default DB credentials together."""
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


def test_reporting_credentials_password_exact_preservation(monkeypatch):
    """Verify reporting password with leading and trailing spaces is preserved exactly without stripping."""
    exact_password = "  secret_reporting_pw_with_spaces  "
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_USER", "  reporting_user  ")
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_PASSWORD", exact_password)

    config = ApiConfig.from_env(use_test_db=False)

    # Username is trimmed/normalized
    assert config.db_config.user == "reporting_user"
    # Password is preserved exactly without strip or modification
    assert config.db_config.password == exact_password

    # Also verify under test-db resolution
    test_config = ApiConfig.from_env(use_test_db=True)
    assert test_config.db_config.user == "reporting_user"
    assert test_config.db_config.password == exact_password


def test_reporting_credentials_username_only_raises(monkeypatch):
    """Verify providing only BANKFLOW_REPORTING_DB_USER raises ApiConfigurationError."""
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_USER", "reporting_user")
    monkeypatch.delenv("BANKFLOW_REPORTING_DB_PASSWORD", raising=False)

    with pytest.raises(ApiConfigurationError) as exc_info:
        ApiConfig.from_env()

    assert "BANKFLOW_REPORTING_DB_PASSWORD is not set" in str(exc_info.value)


def test_reporting_credentials_password_only_raises(monkeypatch):
    """Verify providing only BANKFLOW_REPORTING_DB_PASSWORD raises ApiConfigurationError."""
    monkeypatch.delenv("BANKFLOW_REPORTING_DB_USER", raising=False)
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_PASSWORD", "secret123")

    with pytest.raises(ApiConfigurationError) as exc_info:
        ApiConfig.from_env()

    assert "BANKFLOW_REPORTING_DB_USER is not set" in str(exc_info.value)


@pytest.mark.parametrize("blank_val", ["", "   ", "\t"])
def test_reporting_credentials_blank_username_with_password_raises(monkeypatch, blank_val):
    """Verify blank username with valid password raises ApiConfigurationError without mixing credentials."""
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_USER", blank_val)
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_PASSWORD", "secret123")

    with pytest.raises(ApiConfigurationError) as exc_info:
        ApiConfig.from_env()

    assert "BANKFLOW_REPORTING_DB_USER is blank" in str(exc_info.value)


@pytest.mark.parametrize("blank_val", ["", "   ", "\t"])
def test_reporting_credentials_valid_username_with_blank_password_raises(monkeypatch, blank_val):
    """Verify valid username with blank password raises ApiConfigurationError without mixing credentials."""
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_USER", "reporting_user")
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_PASSWORD", blank_val)

    with pytest.raises(ApiConfigurationError) as exc_info:
        ApiConfig.from_env()

    assert "BANKFLOW_REPORTING_DB_PASSWORD is blank" in str(exc_info.value)


@pytest.mark.parametrize("blank_user,blank_pass", [("", ""), ("   ", "   "), ("\t", "")])
def test_reporting_credentials_both_blank_fallback(monkeypatch, blank_user, blank_pass):
    """Verify when both reporting credentials are blank/whitespace, fallback to standard DB config is preserved."""
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_USER", blank_user)
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_PASSWORD", blank_pass)

    config = ApiConfig.from_env()
    settings = get_settings()

    assert config.db_config.user == settings.db.user
    assert config.db_config.password == settings.db.password


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


def test_bankflow_serve_cli_fails_on_unpaired_reporting_credentials(monkeypatch):
    """Verify 'bankflow serve' exits with code 1 and error message on unpaired reporting credentials."""
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_USER", "unpaired_user")
    monkeypatch.delenv("BANKFLOW_REPORTING_DB_PASSWORD", raising=False)

    runner = CliRunner()
    result = runner.invoke(cli, ["serve"])

    assert result.exit_code == 1
    assert "API Configuration Error" in result.output
    assert "BANKFLOW_REPORTING_DB_PASSWORD is not set" in result.output


def test_api_config_platform_port_and_host_fallback(monkeypatch):
    """Verify platform-assigned PORT and HOST environment variables are used when BANKFLOW_API_* are unset."""
    monkeypatch.delenv("BANKFLOW_API_PORT", raising=False)
    monkeypatch.delenv("BANKFLOW_API_HOST", raising=False)
    monkeypatch.setenv("PORT", "10000")
    monkeypatch.setenv("HOST", "0.0.0.0")

    config = ApiConfig.from_env()
    assert config.port == 10000
    assert config.host == "0.0.0.0"


def test_api_config_reporting_database_url_support(monkeypatch):
    """Verify BANKFLOW_REPORTING_DATABASE_URL connects directly with reporting credentials."""
    reporting_url = "postgresql://bankflow_reporting_user:secret_pw@remote-pg.render.com:5432/reporting_db?sslmode=require"
    monkeypatch.delenv("BANKFLOW_REPORTING_DB_USER", raising=False)
    monkeypatch.delenv("BANKFLOW_REPORTING_DB_PASSWORD", raising=False)
    monkeypatch.setenv("BANKFLOW_REPORTING_DATABASE_URL", reporting_url)

    config = ApiConfig.from_env()
    assert config.db_config.user == "bankflow_reporting_user"
    assert config.db_config.password == "secret_pw"
    assert config.db_config.host == "remote-pg.render.com"
    assert config.db_config.name == "reporting_db"
    assert config.db_config.sslmode == "require"


def test_api_config_preserves_base_db_sslmode_with_reporting_credentials(monkeypatch):
    """Verify sslmode from base database is preserved when dedicated reporting credentials are provided."""
    base_url = "postgresql://admin:admin_pass@ep-cool-fog-123.neon.tech:5432/bankflow?sslmode=require"
    monkeypatch.setenv("DATABASE_URL", base_url)
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_USER", "custom_reporting_role")
    monkeypatch.setenv("BANKFLOW_REPORTING_DB_PASSWORD", "custom_reporting_pass")

    config = ApiConfig.from_env()
    assert config.db_config.user == "custom_reporting_role"
    assert config.db_config.password == "custom_reporting_pass"
    assert config.db_config.sslmode == "require"
    assert "sslmode=require" in config.db_config.get_dsn()
