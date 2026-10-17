"""
FastAPI application factory for the BankFlow Read-Only Reporting API.
"""

from __future__ import annotations

import logging
from typing import List, Optional
from fastapi import APIRouter, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import psycopg2

from bankflow.api.config import ApiConfig
from bankflow.api.routes import (
    batches,
    branch_channel,
    daily,
    deposit_withdrawal,
    health,
    overview,
    quality,
    quarantine,
    transactions,
    type_mix,
)
from bankflow.config import DatabaseConfig

logger = logging.getLogger(__name__)


def create_app(
    db_config: Optional[DatabaseConfig] = None,
    cors_origins: Optional[List[str]] = None,
    use_test_db: bool = False,
) -> FastAPI:
    """
    Constructs the BankFlow read-only reporting API FastAPI application.
    """
    app = FastAPI(
        title="BankFlow Reporting API",
        description="Secure, read-only analytics reporting API for the BankFlow banking transaction warehouse and Lovable console.",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Resolve database configuration
    if db_config is None:
        api_conf = ApiConfig.from_env(use_test_db=use_test_db)
        app.state.db_config = api_conf.db_config
        resolved_origins = list(cors_origins or api_conf.cors_origins)
    else:
        app.state.db_config = db_config
        api_conf = ApiConfig.from_env(use_test_db=use_test_db)
        resolved_origins = list(cors_origins or api_conf.cors_origins)

    # CORS configuration — strictly permitted frontend origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_origins,
        allow_credentials=True,
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
    )

    # Global Exception Handlers
    @app.exception_handler(psycopg2.OperationalError)
    async def operational_error_handler(request: Request, exc: psycopg2.OperationalError):
        logger.error("Database connection/operational error: %s", str(exc))
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Database service is temporarily unavailable. Please retry later."},
        )

    @app.exception_handler(psycopg2.Error)
    async def postgres_error_handler(request: Request, exc: psycopg2.Error):
        logger.error("PostgreSQL query execution error: %s", str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "A database query error occurred while generating reporting metrics."},
        )

    # Root / Info route
    @app.get("/", tags=["System"])
    def root_info():
        return {
            "name": "BankFlow Reporting API",
            "version": "0.1.0",
            "documentation": "/docs",
            "health": "/api/v1/health",
            "frontend_console": "https://bankflow-analytics-console.lovable.app",
        }

    # Mount v1 API endpoints
    v1_router = APIRouter(prefix="/api/v1")
    v1_router.include_router(health.router)
    v1_router.include_router(overview.router)
    v1_router.include_router(daily.router)
    v1_router.include_router(deposit_withdrawal.router)
    v1_router.include_router(branch_channel.router)
    v1_router.include_router(type_mix.router)
    v1_router.include_router(quality.router)
    v1_router.include_router(batches.router)
    v1_router.include_router(quarantine.router)
    v1_router.include_router(transactions.router)

    app.include_router(v1_router)

    return app
