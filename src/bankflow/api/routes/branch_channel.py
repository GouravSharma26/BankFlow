"""
Branch and channel activity endpoint for BankFlow Dashboard.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
import psycopg2

from bankflow.api.db import get_db
from bankflow.api.schemas import BranchChannelItem
from bankflow.api.validators import validate_channel, validate_currency

router = APIRouter(prefix="/branch-channel", tags=["Analytics"])


@router.get("", response_model=List[BranchChannelItem])
def get_branch_channel_activity(
    currency: Optional[str] = Query(None, description="Filter by 3-letter currency code (e.g. USD)"),
    channel: Optional[str] = Query(None, description="Filter by channel (BRANCH, ATM, ONLINE, MOBILE)"),
    branch_id: Optional[str] = Query(None, description="Filter by branch identifier"),
    region: Optional[str] = Query(None, description="Filter by region"),
    limit: int = Query(50, ge=1, le=200, description="Maximum rows to return"),
    conn: psycopg2.extensions.connection = Depends(get_db),
) -> List[BranchChannelItem]:
    """
    Returns branch and channel distribution metrics from reporting.v_branch_channel_activity.
    """
    valid_curr = validate_currency(currency)
    valid_channel = validate_channel(channel)

    sql = """
        SELECT
            region,
            branch_id,
            branch_name,
            channel,
            currency,
            total_transaction_count,
            completed_transaction_count,
            distinct_accounts,
            distinct_customers,
            gross_transaction_amount,
            completed_gross_amount
        FROM reporting.v_branch_channel_activity
        WHERE 1=1
    """
    params = []
    if valid_curr:
        sql += " AND currency = %s"
        params.append(valid_curr)
    if valid_channel:
        sql += " AND channel = %s"
        params.append(valid_channel)
    if branch_id:
        sql += " AND branch_id = %s"
        params.append(branch_id.strip())
    if region:
        sql += " AND region = %s"
        params.append(region.strip())

    sql += " ORDER BY gross_transaction_amount DESC, total_transaction_count DESC LIMIT %s;"
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

    return [
        BranchChannelItem(
            region=r["region"],
            branch_id=r["branch_id"],
            branch_name=r["branch_name"],
            channel=r["channel"],
            currency=r["currency"],
            total_transaction_count=r["total_transaction_count"],
            completed_transaction_count=r["completed_transaction_count"],
            distinct_accounts=r["distinct_accounts"],
            distinct_customers=r["distinct_customers"],
            gross_transaction_amount=f"{r['gross_transaction_amount'] or Decimal('0.00'):.2f}",
            completed_gross_amount=f"{r['completed_gross_amount'] or Decimal('0.00'):.2f}",
        )
        for r in rows
    ]
