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
    # Safe test databases
    assert DatabaseConfig(name="bankflow_test").is_test_database() is True
    assert DatabaseConfig(name="test_db").is_test_database() is True
    assert DatabaseConfig(name="ci_test_warehouse").is_test_database() is True

    # Non-test / unsafe databases
    assert DatabaseConfig(name="bankflow").is_test_database() is False
    assert DatabaseConfig(name="postgres").is_test_database() is False
    assert DatabaseConfig(name="production_warehouse").is_test_database() is False


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
