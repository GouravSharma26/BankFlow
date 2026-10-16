"""
BankFlow configuration management and database safety guards.
Reads configuration from environment variables and optional .env file.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

# Load local .env if present
load_dotenv()


@dataclass(frozen=True)
class DatabaseConfig:
    """PostgreSQL database connection parameters."""
    host: str = "localhost"
    port: int = 5432
    name: str = "bankflow"
    user: str = "postgres"
    password: str = ""
    url: Optional[str] = None

    def __post_init__(self) -> None:
        if self.url:
            parsed = urlparse(self.url)
            if parsed.hostname:
                object.__setattr__(self, "host", parsed.hostname)
            if parsed.port:
                object.__setattr__(self, "port", parsed.port)
            if parsed.path.lstrip("/"):
                object.__setattr__(self, "name", parsed.path.lstrip("/"))
            if parsed.username:
                object.__setattr__(self, "user", parsed.username)
            if parsed.password:
                object.__setattr__(self, "password", parsed.password)

    @classmethod
    def from_url(cls, url: str) -> DatabaseConfig:
        """Construct from a connection URL."""
        parsed = urlparse(url)
        return cls(
            host=parsed.hostname or "localhost",
            port=parsed.port or 5432,
            name=parsed.path.lstrip("/") or "bankflow",
            user=parsed.username or "postgres",
            password=parsed.password or "",
            url=url,
        )

    @classmethod
    def from_env(cls, prefix: str = "BANKFLOW_DB_", url_var: Optional[str] = "DATABASE_URL") -> DatabaseConfig:
        """Construct from environment variables, preferring URL if provided."""
        url = os.getenv(url_var) if url_var else None
        if url:
            return cls.from_url(url)

        host = os.getenv(f"{prefix}HOST", "localhost")
        port_raw = os.getenv(f"{prefix}PORT", "5432")
        try:
            port = int(port_raw)
        except ValueError:
            port = 5432

        name = os.getenv(f"{prefix}NAME", "bankflow")
        user = os.getenv(f"{prefix}USER", "postgres")
        password = os.getenv(f"{prefix}PASSWORD", "")

        return cls(
            host=host,
            port=port,
            name=name,
            user=user,
            password=password,
            url=None,
        )

    def get_dsn(self) -> str:
        """Return psycopg-compatible connection DSN."""
        if self.url:
            return self.url
        parts = [
            f"host={self.host}",
            f"port={self.port}",
            f"dbname={self.name}",
            f"user={self.user}",
        ]
        if self.password:
            parts.append(f"password={self.password}")
        return " ".join(parts)

    def is_test_database(self) -> bool:
        """
        Guardrail check to ensure destructive teardowns only target dedicated test databases.
        Uses strict token-boundary matching to ensure 'test' is an isolated token.
        Rejects substrings like 'latest', 'contest', and any name containing production-like keywords
        (e.g., 'production_test_backup', 'prod', 'live', 'backup', 'master').
        Preserves valid test names such as 'bankflow_test', 'test_db', and 'ci_test_warehouse'.
        """
        lower_name = self.name.lower().strip()
        if not lower_name:
            return False

        # Split on non-alphanumeric boundaries (underscores, hyphens, dots, etc.)
        tokens = [t for t in re.split(r"[^a-zA-Z0-9]+", lower_name) if t]
        if not tokens:
            return False

        # Forbidden production-like tokens: reject immediately regardless of 'test' presence
        FORBIDDEN_PROD_TOKENS = {
            "production",
            "prod",
            "live",
            "backup",
            "master",
            "main",
            "real",
            "postgres",
        }
        if any(token in FORBIDDEN_PROD_TOKENS for token in tokens):
            return False

        # Exact primary application database name without test suffix is rejected
        if lower_name == "bankflow":
            return False

        # Must contain 'test' as an exact, isolated token
        return "test" in tokens

    def assert_safe_for_reset(self) -> None:
        """Raise an error if attempting destructive operations on a non-test database."""
        if not self.is_test_database():
            raise PermissionError(
                f"SAFETY GUARD: Refusing to perform destructive operation on database '{self.name}'. "
                f"Destructive commands are only permitted on dedicated test databases whose name contains 'test'."
            )


@dataclass(frozen=True)
class Settings:
    """BankFlow application settings."""
    db: DatabaseConfig
    test_db: DatabaseConfig
    reporting_timezone: str = "UTC"
    default_currency: str = "USD"
    default_source_system: str = "CORE_BANKING"

    @classmethod
    def load(cls) -> Settings:
        """Load all settings from environment."""
        db = DatabaseConfig.from_env(prefix="BANKFLOW_DB_", url_var="DATABASE_URL")

        # Test DB config: uses BANKFLOW_TEST_DB_NAME or TEST_DATABASE_URL
        test_url = os.getenv("TEST_DATABASE_URL")
        if test_url:
            test_db = DatabaseConfig.from_env(prefix="BANKFLOW_TEST_DB_", url_var="TEST_DATABASE_URL")
        else:
            test_db_name = os.getenv("BANKFLOW_TEST_DB_NAME", f"{db.name}_test")
            test_db = DatabaseConfig(
                host=db.host,
                port=db.port,
                name=test_db_name,
                user=db.user,
                password=db.password,
                url=None,
            )

        tz = os.getenv("BANKFLOW_REPORTING_TIMEZONE", "UTC")
        currency = os.getenv("BANKFLOW_DEFAULT_CURRENCY", "USD")
        source_system = os.getenv("BANKFLOW_DEFAULT_SOURCE_SYSTEM", "CORE_BANKING")

        return cls(
            db=db,
            test_db=test_db,
            reporting_timezone=tz,
            default_currency=currency,
            default_source_system=source_system,
        )


def get_settings() -> Settings:
    """Helper to load application settings."""
    return Settings.load()
