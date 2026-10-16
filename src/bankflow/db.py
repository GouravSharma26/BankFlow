"""
Database connection, session management, and transaction handling.
Uses psycopg2 for direct, efficient PostgreSQL interaction.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, Optional, Tuple

import psycopg2
from psycopg2.extensions import connection as PgConnection

from bankflow.config import DatabaseConfig, get_settings


@contextmanager
def get_connection(config: Optional[DatabaseConfig] = None) -> Generator[PgConnection, None, None]:
    """
    Context manager yielding an active database connection.
    Automatically closes the connection upon exit.
    """
    if config is None:
        config = get_settings().db

    dsn = config.get_dsn()
    conn = psycopg2.connect(dsn)
    try:
        yield conn
    finally:
        if not conn.closed:
            conn.close()


@contextmanager
def transaction(conn: PgConnection) -> Generator[PgConnection, None, None]:
    """
    Transaction scope. Commits on successful block completion, rolls back on exception.
    """
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def check_connection(config: Optional[DatabaseConfig] = None) -> Tuple[bool, str]:
    """
    Check connectivity to the configured database.
    Returns (success, message). Safe against credential leakage.
    """
    if config is None:
        config = get_settings().db

    try:
        with get_connection(config) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return True, f"Successfully connected to database '{config.name}' on {config.host}:{config.port}."
    except Exception as ex:
        # Avoid exposing raw DSN which may contain credentials
        sanitized_msg = str(ex).split("\n")[0]
        return False, f"Failed to connect to '{config.name}' on {config.host}:{config.port}: {sanitized_msg}"
