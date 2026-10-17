"""
Health and status endpoints for BankFlow Reporting API.
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Request, Response, status
import psycopg2

from bankflow.api.schemas import HealthResponse
from bankflow.config import DatabaseConfig

router = APIRouter(prefix="/health", tags=["System"])
logger = logging.getLogger(__name__)


@router.get("", response_model=HealthResponse)
def check_health(request: Request, response: Response) -> HealthResponse:
    """
    Check reporting API health and read-only database connectivity.
    Does not expose sensitive credentials, hostnames, or schema details.
    """
    db_config: DatabaseConfig = request.app.state.db_config
    try:
        conn = psycopg2.connect(
            host=db_config.host,
            port=db_config.port,
            dbname=db_config.name,
            user=db_config.user,
            password=db_config.password,
            connect_timeout=2,
        )
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS healthy;")
                row = cur.fetchone()
                if row and row[0] == 1:
                    return HealthResponse(
                        status="healthy",
                        service="bankflow-reporting-api",
                        version="0.1.0",
                        database="connected",
                    )
        finally:
            conn.close()
    except Exception as e:
        logger.warning("Database health probe failed: %s", str(e))

    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(
        status="degraded",
        service="bankflow-reporting-api",
        version="0.1.0",
        database="unavailable",
    )
