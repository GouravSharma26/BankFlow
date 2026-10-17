"""
Executive overview endpoint for BankFlow Dashboard.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, Query
import psycopg2

from bankflow.api.db import get_db
from bankflow.api.schemas import OverviewCurrencySummary, OverviewResponse
from bankflow.api.validators import validate_currency

router = APIRouter(prefix="/overview", tags=["Analytics"])


@router.get("", response_model=OverviewResponse)
def get_overview(
    currency: Optional[str] = Query(None, description="Filter metrics by 3-letter currency code"),
    conn: psycopg2.extensions.connection = Depends(get_db),
) -> OverviewResponse:
    """
    Returns executive-level summary metrics, currency isolation lists, date ranges, and quality totals.
    All monetary metrics remain strictly grouped by currency.
    """
    valid_curr = validate_currency(currency)

    with conn.cursor() as cur:
        # 1. Currency summaries
        sql = """
            SELECT
                v.currency,
                v.total_transactions,
                v.completed_transactions,
                v.gross_transaction_amount,
                v.completed_gross_amount,
                COALESCE(e.distinct_accounts, 0) AS active_accounts,
                COALESCE(e.distinct_customers, 0) AS active_customers,
                v.min_date,
                v.max_date
            FROM (
                SELECT
                    currency,
                    SUM(total_transaction_count) AS total_transactions,
                    SUM(completed_transaction_count) AS completed_transactions,
                    SUM(gross_transaction_amount)::NUMERIC(18, 2) AS gross_transaction_amount,
                    SUM(completed_gross_amount)::NUMERIC(18, 2) AS completed_gross_amount,
                    MIN(reporting_date)::TEXT AS min_date,
                    MAX(reporting_date)::TEXT AS max_date
                FROM reporting.v_daily_transaction_summary
        """
        params = []
        if valid_curr:
            sql += " WHERE currency = %s"
            params.append(valid_curr)
        sql += """
                GROUP BY currency
            ) v
            LEFT JOIN (
                SELECT
                    currency,
                    COUNT(DISTINCT account_id) AS distinct_accounts,
                    COUNT(DISTINCT customer_id) AS distinct_customers
                FROM reporting.v_transaction_details
        """
        if valid_curr:
            sql += " WHERE currency = %s"
            params.append(valid_curr)
        sql += """
                GROUP BY currency
            ) e ON e.currency = v.currency
            ORDER BY v.currency;
        """

        cur.execute(sql, tuple(params))
        curr_rows = cur.fetchall()

        currency_summaries = []
        all_currencies = []
        earliest_dates = []
        latest_dates = []

        for r in curr_rows:
            all_currencies.append(r["currency"])
            if r["min_date"]:
                earliest_dates.append(r["min_date"])
            if r["max_date"]:
                latest_dates.append(r["max_date"])

            tot = r["total_transactions"] or 0
            comp = r["completed_transactions"] or 0
            rate = f"{(Decimal(comp) / Decimal(tot) * 100):.2f}" if tot > 0 else "0.00"

            currency_summaries.append(
                OverviewCurrencySummary(
                    currency=r["currency"],
                    total_transactions=tot,
                    completed_transactions=comp,
                    gross_transaction_amount=f"{r['gross_transaction_amount'] or Decimal('0.00'):.2f}",
                    completed_gross_amount=f"{r['completed_gross_amount'] or Decimal('0.00'):.2f}",
                    acceptance_rate_pct=rate,
                    active_accounts=r["active_accounts"] or 0,
                    active_customers=r["active_customers"] or 0,
                )
            )

        # 2. Batch metrics
        cur.execute("""
            SELECT
                COUNT(*) AS total_batches,
                (SELECT status FROM reporting.v_pipeline_execution_health ORDER BY started_at DESC NULLS LAST LIMIT 1) AS latest_batch_status
            FROM reporting.v_pipeline_execution_health;
        """)
        batch_info = cur.fetchone() or {"total_batches": 0, "latest_batch_status": None}

        # 3. Quality issues count
        cur.execute("SELECT COALESCE(SUM(issue_count), 0) AS total_issues FROM reporting.v_data_quality_summary;")
        quality_info = cur.fetchone() or {"total_issues": 0}

        # 4. Quarantined records count
        cur.execute("SELECT COALESCE(SUM(quarantined_rows), 0) AS total_quarantined FROM reporting.v_quarantine_inventory;")
        quarantine_info = cur.fetchone() or {"total_quarantined": 0}

        return OverviewResponse(
            currencies=all_currencies,
            earliest_date=min(earliest_dates) if earliest_dates else None,
            latest_date=max(latest_dates) if latest_dates else None,
            metrics_by_currency=currency_summaries,
            total_batches=batch_info["total_batches"] or 0,
            latest_batch_status=batch_info["latest_batch_status"],
            total_quality_issues=quality_info["total_issues"] or 0,
            total_quarantined_records=quarantine_info["total_quarantined"] or 0,
        )
