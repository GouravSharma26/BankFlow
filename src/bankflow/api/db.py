"""
Read-only database connection management for BankFlow Reporting API.
Enforces read-only sessions and statement timeouts for defense-in-depth security.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Generator
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import HTTPException, Request, status

from bankflow.config import DatabaseConfig

logger = logging.getLogger(__name__)


def create_readonly_connection(db_config: DatabaseConfig) -> psycopg2.extensions.connection:
    """
    Establish a connection and enforce read-only transaction mode and query timeout.
    """
    try:
        conn = psycopg2.connect(
            host=db_config.host,
            port=db_config.port,
            dbname=db_config.name,
            user=db_config.user,
            password=db_config.password,
            cursor_factory=RealDictCursor,
            connect_timeout=5,
        )
        # Defense in depth: session-level read-only and statement timeout
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '5000ms'")
        return conn
    except psycopg2.OperationalError as e:
        logger.error("Failed to connect to database in read-only mode: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service is currently unavailable. Please try again later.",
        ) from None
    except Exception as e:
        logger.error("Unexpected database initialization error: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal database configuration error.",
        ) from None


@contextmanager
def readonly_db_session(db_config: DatabaseConfig) -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager for safe read-only database connections."""
    conn = create_readonly_connection(db_config)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get_db(request: Request) -> Generator[psycopg2.extensions.connection, None, None]:
    """FastAPI dependency yielding a read-only database connection."""
    db_config: DatabaseConfig = request.app.state.db_config
    conn = create_readonly_connection(db_config)
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass
