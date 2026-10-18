"""
Unit tests for BankFlow configuration and database safety guardrails.
"""

import pytest

from bankflow.config import DatabaseConfig, Settings


def test_database_config_defaults():
    cfg = DatabaseConfig(host="localhost", port=5432, name="bankflow", user="postgres")
    assert cfg.host == "localhost"
    assert cfg.port == 5432
    assert cfg.name == "bankflow"
    assert cfg.user == "postgres"
    assert "host=localhost" in cfg.get_dsn()
    assert "dbname=bankflow" in cfg.get_dsn()


def test_database_config_from_url(monkeypatch):
    url = "postgresql://myuser:mypass@dbhost:5433/bankflow_custom"

    # 1. Test direct constructor with url parameter (parsed via post_init)
    cfg_direct = DatabaseConfig(url=url)
    assert cfg_direct.host == "dbhost"
    assert cfg_direct.port == 5433
    assert cfg_direct.name == "bankflow_custom"
    assert cfg_direct.user == "myuser"
    assert cfg_direct.password == "mypass"
    assert cfg_direct.get_dsn() == url

    # 2. Test from_url class method
    cfg_helper = DatabaseConfig.from_url(url)
    assert cfg_helper.host == "dbhost"
    assert cfg_helper.port == 5433
    assert cfg_helper.name == "bankflow_custom"
    assert cfg_helper.user == "myuser"
    assert cfg_helper.password == "mypass"
    assert cfg_helper.get_dsn() == url

    # 3. Test from_env reading an actual environment variable
    monkeypatch.setenv("TEST_APP_DB_URL", url)
    cfg_env = DatabaseConfig.from_env(url_var="TEST_APP_DB_URL")
    assert cfg_env.host == "dbhost"
    assert cfg_env.port == 5433
    assert cfg_env.name == "bankflow_custom"
    assert cfg_env.user == "myuser"
    assert cfg_env.password == "mypass"
    assert cfg_env.get_dsn() == url


def test_is_test_database_guard():
    # Safe test databases (strict token boundary matches)
    assert DatabaseConfig(name="bankflow_test").is_test_database() is True
    assert DatabaseConfig(name="test_db").is_test_database() is True
    assert DatabaseConfig(name="ci_test_warehouse").is_test_database() is True
    assert DatabaseConfig(name="bankflow-test").is_test_database() is True
    assert DatabaseConfig(name="test").is_test_database() is True

    # Substrings containing 'test' as a non-token must be rejected
    assert DatabaseConfig(name="latest").is_test_database() is False
    assert DatabaseConfig(name="contest").is_test_database() is False
    assert DatabaseConfig(name="attest").is_test_database() is False
    assert DatabaseConfig(name="detest_db").is_test_database() is False
    assert DatabaseConfig(name="greatest_app").is_test_database() is False

    # Production-like and unsafe keywords must be rejected even if 'test' token is present
    assert DatabaseConfig(name="production_test_backup").is_test_database() is False
    assert DatabaseConfig(name="prod_test").is_test_database() is False
    assert DatabaseConfig(name="test_live").is_test_database() is False
    assert DatabaseConfig(name="test_backup").is_test_database() is False
    assert DatabaseConfig(name="master_test").is_test_database() is False
    assert DatabaseConfig(name="main_test_db").is_test_database() is False
    assert DatabaseConfig(name="staging_test").is_test_database() is False
    assert DatabaseConfig(name="stage_test").is_test_database() is False
    assert DatabaseConfig(name="release_test").is_test_database() is False

    # Standard production / non-test databases
    assert DatabaseConfig(name="bankflow").is_test_database() is False
    assert DatabaseConfig(name="postgres").is_test_database() is False
    assert DatabaseConfig(name="production_warehouse").is_test_database() is False
    assert DatabaseConfig(name="").is_test_database() is False


def test_assert_safe_for_reset_raises_on_production():
    prod_cfg = DatabaseConfig(name="bankflow")
    with pytest.raises(PermissionError) as exc_info:
        prod_cfg.assert_safe_for_reset()
    assert "SAFETY GUARD" in str(exc_info.value)
    assert "bankflow" in str(exc_info.value)

    test_cfg = DatabaseConfig(name="bankflow_test")
    # Should not raise
    test_cfg.assert_safe_for_reset()


def test_settings_load_defaults():
    settings = Settings.load()
    assert settings.db is not None
    assert settings.test_db is not None
    assert settings.test_db.is_test_database() is True
    assert settings.reporting_timezone == "UTC"
    assert settings.default_currency == "USD"


def test_database_config_sslmode_parsing(monkeypatch):
    """Verify sslmode is parsed from query parameters in connection URL and from environment variables."""
    # From URL query parameters
    url_with_ssl = "postgresql://user:pass@ep-cool-fog-123.neon.tech:5432/bankflow?sslmode=require"
    cfg = DatabaseConfig.from_url(url_with_ssl)
    assert cfg.sslmode == "require"
    assert "sslmode=require" in cfg.get_dsn()

    # From direct constructor with url
    cfg_direct = DatabaseConfig(url=url_with_ssl)
    assert cfg_direct.sslmode == "require"

    # From environment variable prefix
    monkeypatch.setenv("CUSTOM_DB_HOST", "cloudhost")
    monkeypatch.setenv("CUSTOM_DB_NAME", "clouddb")
    monkeypatch.setenv("CUSTOM_DB_SSLMODE", "verify-full")
    cfg_env = DatabaseConfig.from_env(prefix="CUSTOM_DB_", url_var="NONEXISTENT_URL")
    assert cfg_env.sslmode == "verify-full"
    assert "sslmode=verify-full" in cfg_env.get_dsn()
