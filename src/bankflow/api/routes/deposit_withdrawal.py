"""
Deposit versus withdrawal cash-flow analysis endpoint for BankFlow Dashboard.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
import psycopg2

from bankflow.api.db import get_db
from bankflow.api.schemas import DepositWithdrawalItem
from bankflow.api.validators import validate_currency, validate_date_range

router = APIRouter(prefix="/deposit-withdrawal", tags=["Analytics"])


@router.get("", response_model=List[DepositWithdrawalItem])
def get_deposit_withdrawal_analysis(
    currency: Optional[str] = Query(None, description="Filter by 3-letter currency code (e.g. USD)"),
    start_date: Optional[str] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date filter (YYYY-MM-DD)"),
    limit: int = Query(30, ge=1, le=365, description="Maximum rows to return"),
    conn: psycopg2.extensions.connection = Depends(get_db),
) -> List[DepositWithdrawalItem]:
    """
    Returns deposit versus withdrawal activity and completed value shares from reporting.v_deposit_withdrawal_analysis.
    """
    valid_curr = validate_currency(currency)
    start_d, end_d = validate_date_range(start_date, end_date)

    sql = """
        SELECT
            date_key,
            reporting_date::TEXT,
            currency,
            deposit_count,
            deposit_gross_amount,
            completed_deposit_count,
            completed_deposit_gross_amount,
            withdrawal_count,
            withdrawal_gross_amount,
            completed_withdrawal_count,
            completed_withdrawal_gross_amount,
            reversal_count,
            reversal_gross_amount
        FROM reporting.v_deposit_withdrawal_analysis
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

    items = []
    for r in rows:
        dep_val = r["completed_deposit_gross_amount"] or Decimal("0.00")
        wth_val = r["completed_withdrawal_gross_amount"] or Decimal("0.00")
        total_val = dep_val + wth_val

        if total_val > Decimal("0.00"):
            dep_pct = f"{(dep_val / total_val * 100):.2f}"
            wth_pct = f"{(wth_val / total_val * 100):.2f}"
        else:
            dep_pct = "0.00"
            wth_pct = "0.00"

        items.append(
            DepositWithdrawalItem(
                date_key=r["date_key"],
                reporting_date=r["reporting_date"],
                currency=r["currency"],
                deposit_count=r["deposit_count"],
                deposit_gross_amount=f"{r['deposit_gross_amount'] or Decimal('0.00'):.2f}",
                completed_deposit_count=r["completed_deposit_count"],
                completed_deposit_gross_amount=f"{dep_val:.2f}",
                withdrawal_count=r["withdrawal_count"],
                withdrawal_gross_amount=f"{r['withdrawal_gross_amount'] or Decimal('0.00'):.2f}",
                completed_withdrawal_count=r["completed_withdrawal_count"],
                completed_withdrawal_gross_amount=f"{wth_val:.2f}",
                reversal_count=r["reversal_count"],
                reversal_gross_amount=f"{r['reversal_gross_amount'] or Decimal('0.00'):.2f}",
                deposit_value_share_pct=dep_pct,
                withdrawal_value_share_pct=wth_pct,
            )
        )

    return items
