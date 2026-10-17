"""
Transaction type mix endpoint for BankFlow Dashboard.
"""

from __future__ import annotations

from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
import psycopg2

from bankflow.api.db import get_db
from bankflow.api.schemas import TypeMixItem
from bankflow.api.validators import validate_currency

router = APIRouter(prefix="/type-mix", tags=["Analytics"])


@router.get("", response_model=List[TypeMixItem])
def get_transaction_type_mix(
    currency: Optional[str] = Query(None, description="Filter by 3-letter currency code (e.g. USD)"),
    conn: psycopg2.extensions.connection = Depends(get_db),
) -> List[TypeMixItem]:
    """
    Returns transaction type portfolio breakdown, event share, and value share from reporting.v_transaction_type_mix.
    """
    valid_curr = validate_currency(currency)

    sql = """
        SELECT
            transaction_type_code,
            transaction_type_name,
            transaction_family,
            currency,
            total_transaction_count,
            completed_transaction_count,
            failed_transaction_count,
            pending_transaction_count,
            reversed_transaction_count,
            gross_transaction_amount,
            completed_gross_amount
        FROM reporting.v_transaction_type_mix
    """
    params = []
    if valid_curr:
        sql += " WHERE currency = %s"
        params.append(valid_curr)
    sql += " ORDER BY gross_transaction_amount DESC, total_transaction_count DESC;"

    with conn.cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

    # Compute totals per currency to calculate percentage shares
    currency_totals = {}
    for r in rows:
        curr = r["currency"]
        if curr not in currency_totals:
            currency_totals[curr] = {"count": 0, "value": Decimal("0.00")}
        currency_totals[curr]["count"] += r["total_transaction_count"] or 0
        currency_totals[curr]["value"] += r["gross_transaction_amount"] or Decimal("0.00")

    items = []
    for r in rows:
        curr = r["currency"]
        t_count = currency_totals[curr]["count"]
        t_val = currency_totals[curr]["value"]

        row_count = r["total_transaction_count"] or 0
        row_val = r["gross_transaction_amount"] or Decimal("0.00")

        event_share = f"{(Decimal(row_count) / Decimal(t_count) * 100):.2f}" if t_count > 0 else "0.00"
        value_share = f"{(row_val / t_val * 100):.2f}" if t_val > Decimal("0.00") else "0.00"

        items.append(
            TypeMixItem(
                transaction_type_code=r["transaction_type_code"],
                transaction_type_name=r["transaction_type_name"],
                transaction_family=r["transaction_family"],
                currency=r["currency"],
                total_transaction_count=row_count,
                completed_transaction_count=r["completed_transaction_count"] or 0,
                failed_transaction_count=r["failed_transaction_count"] or 0,
                pending_transaction_count=r["pending_transaction_count"] or 0,
                reversed_transaction_count=r["reversed_transaction_count"] or 0,
                gross_transaction_amount=f"{row_val:.2f}",
                completed_gross_amount=f"{r['completed_gross_amount'] or Decimal('0.00'):.2f}",
                event_share_pct=event_share,
                value_share_pct=value_share,
            )
        )

    return items
