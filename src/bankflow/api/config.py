"""
Configuration for the BankFlow Read-Only Reporting API.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from bankflow.config import DatabaseConfig, get_settings


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
    def from_env(cls, use_test_db: bool = False) -> ApiConfig:
        host = os.environ.get("BANKFLOW_API_HOST", "127.0.0.1")
        port = int(os.environ.get("BANKFLOW_API_PORT", "8000"))

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

        # Dedicated reporting credentials if configured, otherwise standard DB config
        reporting_user = os.environ.get("BANKFLOW_REPORTING_DB_USER")
        reporting_password = os.environ.get("BANKFLOW_REPORTING_DB_PASSWORD")

        settings = get_settings()
        db_conf = settings.test_db if use_test_db else settings.db
        if reporting_user and reporting_password:
            db_conf = DatabaseConfig(
                host=db_conf.host,
                port=db_conf.port,
                name=db_conf.name,
                user=reporting_user,
                password=reporting_password,
            )


        return cls(
            host=host,
            port=port,
            cors_origins=cors_origins,
            db_config=db_conf,
        )
