"""
Pipeline execution health and batch monitoring endpoint for BankFlow Dashboard.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
import psycopg2

from bankflow.api.db import get_db
from bankflow.api.schemas import BatchExecutionItem
from bankflow.api.validators import validate_reconciliation_status

router = APIRouter(prefix="/batches", tags=["Monitoring"])


@router.get("", response_model=List[BatchExecutionItem])
def get_batch_execution_health(
    status: Optional[str] = Query(None, description="Filter by batch status (e.g. SUCCEEDED, FAILED)"),
    reconciliation_status: Optional[str] = Query(None, description="Filter by reconciliation status"),
    limit: int = Query(20, ge=1, le=100, description="Maximum batches to return"),
    conn: psycopg2.extensions.connection = Depends(get_db),
) -> List[BatchExecutionItem]:
    """
    Returns ETL batch execution health, row accounting, durations, and reconciliation status from reporting.v_pipeline_execution_health.
    """
    valid_recon = validate_reconciliation_status(reconciliation_status)

    sql = """
        SELECT
            batch_id,
            source_name,
            started_at::TEXT,
            completed_at::TEXT,
            duration_seconds,
            status,
            records_extracted,
            records_staged,
            records_valid,
            records_rejected,
            records_inserted,
            records_updated,
            records_skipped,
            rejection_rate_pct,
            reconciliation_status,
            error_summary
        FROM reporting.v_pipeline_execution_health
        WHERE 1=1
    """
    params = []
    if status:
        sql += " AND status = %s"
        params.append(status.strip().upper())
    if valid_recon:
        sql += " AND reconciliation_status = %s"
        params.append(valid_recon)

    sql += " ORDER BY started_at DESC NULLS LAST, batch_id DESC LIMIT %s;"
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

    return [
        BatchExecutionItem(
            batch_id=r["batch_id"],
            source_name=r["source_name"],
            started_at=r["started_at"],
            completed_at=r["completed_at"],
            duration_seconds=float(r["duration_seconds"]) if r["duration_seconds"] is not None else None,
            status=r["status"],
            records_extracted=r["records_extracted"],
            records_staged=r["records_staged"],
            records_valid=r["records_valid"],
            records_rejected=r["records_rejected"],
            records_inserted=r["records_inserted"],
            records_updated=r["records_updated"],
            records_skipped=r["records_skipped"],
            rejection_rate_pct=f"{r['rejection_rate_pct'] or Decimal('0.00'):.2f}",
            reconciliation_status=r["reconciliation_status"],
            error_summary=r["error_summary"],
        )
        for r in rows
    ]
