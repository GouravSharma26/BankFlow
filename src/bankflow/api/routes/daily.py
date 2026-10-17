"""
Daily transaction activity trends endpoint for BankFlow Dashboard.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
import psycopg2

from bankflow.api.db import get_db
from bankflow.api.schemas import DailyTrendItem
from bankflow.api.validators import validate_currency, validate_date_range

router = APIRouter(prefix="/daily", tags=["Analytics"])


@router.get("", response_model=List[DailyTrendItem])
def get_daily_trends(
    currency: Optional[str] = Query(None, description="Filter by 3-letter currency code (e.g. USD)"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    limit: int = Query(30, ge=1, le=365, description="Maximum daily rows to return"),
    conn: psycopg2.extensions.connection = Depends(get_db),
) -> List[DailyTrendItem]:
    """
    Returns daily transaction trends, counts, active accounts, and gross values from reporting.v_daily_transaction_summary.
    """
    valid_curr = validate_currency(currency)
    start_d, end_d = validate_date_range(start_date, end_date)

    sql = """
        SELECT
            date_key,
            reporting_date::TEXT,
            year_number,
            month_number,
            month_name,
            day_name,
            is_weekend,
            currency,
            total_transaction_count,
            completed_transaction_count,
            pending_transaction_count,
            failed_transaction_count,
            reversed_transaction_count,
            active_accounts,
            active_customers,
            gross_transaction_amount,
            completed_gross_amount
        FROM reporting.v_daily_transaction_summary
        WHERE 1=1
    """
    params = []
    if valid_curr:
        sql += " AND currency = %s"
        params.append(valid_curr)
    if start_d:
        sql += " AND reporting_date >= %s"
        params.append(start_d)
    if end_d:
        sql += " AND reporting_date <= %s"
        params.append(end_d)

    sql += " ORDER BY reporting_date DESC, currency ASC LIMIT %s;"
    params.append(limit)

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

    return [
        DailyTrendItem(
            date_key=r["date_key"],
            reporting_date=r["reporting_date"],
            year_number=r["year_number"],
            month_number=r["month_number"],
            month_name=r["month_name"],
            day_name=r["day_name"],
            is_weekend=r["is_weekend"],
            currency=r["currency"],
            total_transaction_count=r["total_transaction_count"],
            completed_transaction_count=r["completed_transaction_count"],
            pending_transaction_count=r["pending_transaction_count"],
            failed_transaction_count=r["failed_transaction_count"],
            reversed_transaction_count=r["reversed_transaction_count"],
            active_accounts=r["active_accounts"],
            active_customers=r["active_customers"],
            gross_transaction_amount=f"{r['gross_transaction_amount'] or Decimal('0.00'):.2f}",
            completed_gross_amount=f"{r['completed_gross_amount'] or Decimal('0.00'):.2f}",
        )
        for r in rows
    ]
