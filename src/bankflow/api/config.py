"""
Configuration for the BankFlow Read-Only Reporting API.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
from bankflow.config import DatabaseConfig, get_settings


class ApiConfigurationError(ValueError):
    """Raised when API configuration parameters or credentials are invalid."""


@dataclass(frozen=True)
class ApiConfig:
    """Settings for the FastAPI reporting server."""
    host: str = "127.0.0.1"
    port: int = 8000
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "https://bankflow-analytics-console.lovable.app",
    )
    db_config: DatabaseConfig = None

    @classmethod
    def from_env(
        cls,
        use_test_db: bool = False,
        host: Optional[str] = None,
        port: Optional[int] = None,
    ) -> ApiConfig:
        env_host = os.environ.get("BANKFLOW_API_HOST", "127.0.0.1")
        env_port_raw = os.environ.get("BANKFLOW_API_PORT", "8000")
        try:
            env_port = int(env_port_raw)
        except ValueError:
            env_port = 8000

        resolved_host = host if host is not None else env_host
        resolved_port = port if port is not None else env_port

        raw_origins = os.environ.get("BANKFLOW_CORS_ORIGINS", "")
        if raw_origins.strip():
            cors_origins = tuple(o.strip() for o in raw_origins.split(",") if o.strip())
        else:
            cors_origins = (
                "http://localhost:5173",
                "http://localhost:3000",
                "http://127.0.0.1:5173",
                "http://127.0.0.1:3000",
                "https://bankflow-analytics-console.lovable.app",
            )

        # Dedicated reporting credentials resolution
        # Rules:
        # 1. If neither variable is configured (or both are blank), preserve fallback to standard DB config.
        # 2. If both are provided and non-empty, use them together for dedicated reporting role.
        # 3. If only one is configured, or either value is blank while the other is supplied, raise a clear error.
        raw_user = os.environ.get("BANKFLOW_REPORTING_DB_USER")
        raw_password = os.environ.get("BANKFLOW_REPORTING_DB_PASSWORD")

        user_present = raw_user is not None
        password_present = raw_password is not None

        user_non_empty = bool(raw_user and raw_user.strip())
        password_non_empty = bool(raw_password and raw_password.strip())

        settings = get_settings()
        base_db = settings.test_db if use_test_db else settings.db

        if user_present != password_present:
            if user_present:
                raise ApiConfigurationError(
                    "Invalid reporting database configuration: BANKFLOW_REPORTING_DB_USER is configured, "
                    "but BANKFLOW_REPORTING_DB_PASSWORD is not set. Both reporting credentials must be configured together."
                )
            else:
                raise ApiConfigurationError(
                    "Invalid reporting database configuration: BANKFLOW_REPORTING_DB_PASSWORD is configured, "
                    "but BANKFLOW_REPORTING_DB_USER is not set. Both reporting credentials must be configured together."
                )

        if user_non_empty and password_non_empty:
            # Both provided and non-empty: use them together
            db_conf = DatabaseConfig(
                host=base_db.host,
                port=base_db.port,
                name=base_db.name,
                user=raw_user.strip(),
                password=raw_password.strip(),
            )
        elif user_non_empty != password_non_empty:
            # One is supplied non-empty while the other is blank/whitespace
            if user_non_empty:
                raise ApiConfigurationError(
                    "Invalid reporting database configuration: BANKFLOW_REPORTING_DB_USER is supplied, "
                    "but BANKFLOW_REPORTING_DB_PASSWORD is blank. Both credentials must be non-empty."
                )
            else:
                raise ApiConfigurationError(
                    "Invalid reporting database configuration: BANKFLOW_REPORTING_DB_PASSWORD is supplied, "
                    "but BANKFLOW_REPORTING_DB_USER is blank. Both credentials must be non-empty."
                )
        else:
            # Neither is configured with a non-empty value: fallback to standard database configuration
            db_conf = base_db

        return cls(
            host=resolved_host,
            port=resolved_port,
            cors_origins=cors_origins,
            db_config=db_conf,
        )
