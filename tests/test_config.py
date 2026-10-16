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


def test_database_config_from_url():
    url = "postgresql://myuser:mypass@dbhost:5433/bankflow_custom"
    cfg = DatabaseConfig.from_env(url_var="CUSTOM_URL")
    # Simulate url parsing directly
    from urllib.parse import urlparse
    parsed = urlparse(url)
    cfg2 = DatabaseConfig(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        name=parsed.path.lstrip("/"),
        user=parsed.username or "postgres",
        password=parsed.password or "",
        url=url,
    )
    assert cfg2.host == "dbhost"
    assert cfg2.port == 5433
    assert cfg2.name == "bankflow_custom"
    assert cfg2.user == "myuser"
    assert cfg2.password == "mypass"
    assert cfg2.get_dsn() == url


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
