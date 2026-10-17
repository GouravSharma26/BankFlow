"""
Paginated, filterable transaction details endpoint for BankFlow Dashboard.
Exposes conformed analytical transaction fields without raw payloads or personal customer data.
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
import psycopg2

from bankflow.api.db import get_db
from bankflow.api.schemas import PaginatedTransactionsResponse, TransactionDetailItem
from bankflow.api.validators import (
    validate_channel,
    validate_currency,
    validate_date_range,
    validate_status,
    validate_transaction_type,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])

ALLOWED_SORT_COLUMNS = {
    "transaction_timestamp": "transaction_timestamp",
    "amount": "amount",
    "transaction_id": "transaction_id",
    "reporting_date": "reporting_date",
}


@router.get("", response_model=PaginatedTransactionsResponse)
def get_transactions(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(25, ge=1, le=100, description="Items per page"),
    currency: Optional[str] = Query(None, description="Filter by 3-letter currency code (e.g. USD)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (COMPLETED, PENDING, FAILED, REVERSED)"),
    transaction_type: Optional[str] = Query(None, description="Filter by transaction type (DEPOSIT, WITHDRAWAL, etc.)"),
    channel: Optional[str] = Query(None, description="Filter by channel (BRANCH, ATM, ONLINE, MOBILE)"),
    start_date: Optional[str] = Query(None, description="Filter by start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (YYYY-MM-DD)"),
    sort_by: str = Query("transaction_timestamp", description="Sort column (transaction_timestamp, amount, transaction_id, reporting_date)"),
    sort_order: str = Query("desc", description="Sort order ('asc' or 'desc')"),
    conn: psycopg2.extensions.connection = Depends(get_db),
) -> PaginatedTransactionsResponse:
    """
    Returns paginated, sorted, and filtered transaction details from reporting.v_transaction_details.
    """
    valid_curr = validate_currency(currency)
    valid_status = validate_status(status_filter)
    valid_type = validate_transaction_type(transaction_type)
    valid_channel = validate_channel(channel)
    start_d, end_d = validate_date_range(start_date, end_date)

    sort_col = sort_by.strip().lower()
    if sort_col not in ALLOWED_SORT_COLUMNS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort_by '{sort_by}'. Permitted columns: {sorted(ALLOWED_SORT_COLUMNS.keys())}.",
        )
    safe_col = ALLOWED_SORT_COLUMNS[sort_col]

    order_dir = sort_order.strip().lower()
    if order_dir not in {"asc", "desc"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sort_order '{sort_order}'. Permitted values: ['asc', 'desc'].",
        )
    safe_order = "DESC" if order_dir == "desc" else "ASC"

    # Base query filters
    where_clauses = ["1=1"]
    params = []

    if valid_curr:
        where_clauses.append("currency = %s")
        params.append(valid_curr)
    if valid_status:
        where_clauses.append("status = %s")
        params.append(valid_status)
    if valid_type:
        where_clauses.append("transaction_type = %s")
        params.append(valid_type)
    if valid_channel:
        where_clauses.append("channel = %s")
        params.append(valid_channel)
    if start_d:
        where_clauses.append("reporting_date >= %s")
        params.append(start_d)
    if end_d:
        where_clauses.append("reporting_date <= %s")
        params.append(end_d)

    where_str = " AND ".join(where_clauses)

    with conn.cursor() as cur:
        # Count total matching rows
        count_sql = f"SELECT COUNT(*) AS total FROM reporting.v_transaction_details WHERE {where_str};"
        cur.execute(count_sql, tuple(params))
        total = cur.fetchone()["total"]

        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT
                transaction_id,
                source_system,
                account_id,
                customer_id,
                branch_id,
                branch_name,
                region,
                transaction_type,
                type_name,
                transaction_family,
                amount,
                currency,
                status,
                channel,
                transaction_timestamp::TEXT,
                reporting_date::TEXT,
                batch_id,
                loaded_at::TEXT
            FROM reporting.v_transaction_details
            WHERE {where_str}
            ORDER BY {safe_col} {safe_order}, transaction_id {safe_order}
            LIMIT %s OFFSET %s;
        """
        data_params = list(params)
        data_params.extend([page_size, offset])

        cur.execute(data_sql, tuple(data_params))
        rows = cur.fetchall()

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    items = [
        TransactionDetailItem(
            transaction_id=r["transaction_id"],
            source_system=r["source_system"],
            account_id=r["account_id"],
            customer_id=r["customer_id"],
            branch_id=r["branch_id"],
            branch_name=r["branch_name"],
            region=r["region"],
            transaction_type=r["transaction_type"],
            type_name=r["type_name"],
            transaction_family=r["transaction_family"],
            amount=f"{r['amount'] or Decimal('0.00'):.2f}",
            currency=r["currency"],
            status=r["status"],
            channel=r["channel"],
            transaction_timestamp=r["transaction_timestamp"],
            reporting_date=r["reporting_date"],
            batch_id=r["batch_id"],
            loaded_at=r["loaded_at"],
        )
        for r in rows
    ]

    return PaginatedTransactionsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )
