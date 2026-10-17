"""
Data quality summary endpoint for BankFlow Dashboard.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
import psycopg2

from bankflow.api.db import get_db
from bankflow.api.schemas import QualitySummaryItem
from bankflow.api.validators import validate_disposition, validate_severity

router = APIRouter(prefix="/quality", tags=["Analytics"])


@router.get("", response_model=List[QualitySummaryItem])
def get_quality_summary(
    severity: Optional[str] = Query(None, description="Filter by severity (ERROR, WARNING, INFO)"),
    disposition: Optional[str] = Query(None, description="Filter by disposition (ACCEPTED, REJECTED, WARNED, SKIPPED)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum rows to return"),
    conn: psycopg2.extensions.connection = Depends(get_db),
) -> List[QualitySummaryItem]:
    """
    Returns data quality issue metrics separating issue records from affected source rows from reporting.v_data_quality_summary.
    """
    valid_sev = validate_severity(severity)
    valid_disp = validate_disposition(disposition)

    sql = """
        SELECT
            rule_code,
            severity,
            disposition,
            issue_count,
            affected_source_rows,
            affected_batches
        FROM reporting.v_data_quality_summary
        WHERE 1=1
    """
    params = []
    if valid_sev:
        sql += " AND severity = %s"
        params.append(valid_sev)
    if valid_disp:
        sql += " AND disposition = %s"
        params.append(valid_disp)

    sql += " ORDER BY issue_count DESC, affected_source_rows DESC LIMIT %s;"
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

    return [
        QualitySummaryItem(
            rule_code=r["rule_code"],
            severity=r["severity"],
            disposition=r["disposition"],
            issue_count=r["issue_count"],
            affected_source_rows=r["affected_source_rows"],
            affected_batches=r["affected_batches"],
        )
        for r in rows
    ]
