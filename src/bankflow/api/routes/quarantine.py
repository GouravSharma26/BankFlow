"""
Quarantined record inventory endpoint for BankFlow Dashboard.
"""

from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
import psycopg2

from bankflow.api.db import get_db
from bankflow.api.schemas import QuarantineItem
from bankflow.api.validators import validate_entity_type

router = APIRouter(prefix="/quarantine", tags=["Quality"])


@router.get("", response_model=List[QuarantineItem])
def get_quarantine_inventory(
    batch_id: Optional[str] = Query(None, description="Filter by batch identifier"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type (TRANSACTION, CUSTOMER, etc.)"),
    primary_rule_code: Optional[str] = Query(None, description="Filter by primary rule code"),
    limit: int = Query(50, ge=1, le=200, description="Maximum rows to return"),
    conn: psycopg2.extensions.connection = Depends(get_db),
) -> List[QuarantineItem]:
    """
    Returns quarantined records inventory grouped by batch, entity, and rule code from reporting.v_quarantine_inventory.
    """
    valid_entity = validate_entity_type(entity_type)

    sql = """
        SELECT
            batch_id,
            entity_type,
            primary_rule_code,
            quarantined_rows,
            recorded_issue_count,
            first_quarantined_at::TEXT,
            last_quarantined_at::TEXT
        FROM reporting.v_quarantine_inventory
        WHERE 1=1
    """
    params = []
    if batch_id:
        sql += " AND batch_id = %s"
        params.append(batch_id.strip())
    if valid_entity:
        sql += " AND entity_type = %s"
        params.append(valid_entity)
    if primary_rule_code:
        sql += " AND primary_rule_code = %s"
        params.append(primary_rule_code.strip())

    sql += " ORDER BY quarantined_rows DESC, recorded_issue_count DESC LIMIT %s;"
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

    return [
        QuarantineItem(
            batch_id=r["batch_id"],
            entity_type=r["entity_type"],
            primary_rule_code=r["primary_rule_code"],
            quarantined_rows=r["quarantined_rows"],
            recorded_issue_count=r["recorded_issue_count"],
            first_quarantined_at=r["first_quarantined_at"],
            last_quarantined_at=r["last_quarantined_at"],
        )
        for r in rows
    ]
