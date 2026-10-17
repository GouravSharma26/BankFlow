"""
Configuration for the BankFlow Read-Only Reporting API.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
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

        # Dedicated reporting credentials if configured, otherwise standard DB config
        reporting_user = os.environ.get("BANKFLOW_REPORTING_DB_USER")
        reporting_password = os.environ.get("BANKFLOW_REPORTING_DB_PASSWORD")

        settings = get_settings()
        db_conf = settings.test_db if use_test_db else settings.db

        user = reporting_user.strip() if reporting_user and reporting_user.strip() else db_conf.user
        password = reporting_password if reporting_password is not None else db_conf.password

        if (reporting_user and reporting_user.strip()) or (reporting_password is not None):
            db_conf = DatabaseConfig(
                host=db_conf.host,
                port=db_conf.port,
                name=db_conf.name,
                user=user,
                password=password,
            )

        return cls(
            host=resolved_host,
            port=resolved_port,
            cors_origins=cors_origins,
            db_config=db_conf,
        )
