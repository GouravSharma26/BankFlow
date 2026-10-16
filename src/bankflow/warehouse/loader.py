"""
Warehouse Loading Engine.
Loads conformed dimensions and transaction facts from staging to PostgreSQL warehouse.
Enforces database-level idempotency, transactional consistency, and reconciliation audit.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import List, Tuple

import psycopg2
from psycopg2.extras import execute_batch

from bankflow.constants import (
    BATCH_STATUS_FAILED,
    BATCH_STATUS_PENDING,
    BATCH_STATUS_RUNNING,
    BATCH_STATUS_SUCCEEDED,
    BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS,
    DISPOSITION_REJECTED,
    DISPOSITION_SKIPPED,
    RULE_CONFLICTING_REPLAY_PAYLOAD,
    RULE_SOURCE_REPLAY_SKIPPED,
    SEVERITY_ERROR,
    SEVERITY_INFO,
)
from bankflow.db import transaction
from bankflow.warehouse.models import WarehouseLoadingSummary
from bankflow.warehouse.reconciliation import ReconciliationEngine
from bankflow.warehouse.schema import init_warehouse_schema


PERMITTED_LOAD_STATUSES = (BATCH_STATUS_SUCCEEDED, BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS)


class WarehouseLoader:
    """
    Loads validated staging records into the dimensional warehouse layer.
    Ensures dimensions are loaded before facts and enforces replay idempotency.
    """

    def __init__(self, conn: psycopg2.extensions.connection):
        self.conn = conn

    def load_batch(self, batch_id: str) -> WarehouseLoadingSummary:
        """
        Load validated records for the given batch into the warehouse.
        Dimensions: branches -> customers -> accounts.
        Facts: fact_transactions (idempotent; duplicate source events are safely skipped).
        Runs reconciliation at completion and updates batch operational metadata.
        """
        init_warehouse_schema(self.conn)
        summary = WarehouseLoadingSummary(batch_id=batch_id)

        with transaction(self.conn):
            with self.conn.cursor() as cur:
                # 1. Lock and verify batch lifecycle eligibility using strict allowlist
                cur.execute("""
                    SELECT status, validated_at, records_staged, records_valid, records_rejected
                    FROM monitoring.etl_batch_runs
                    WHERE batch_id = %s
                    FOR UPDATE;
                """, (batch_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Batch with ID '{batch_id}' not found in monitoring.etl_batch_runs.")

                status, validated_at, staged, valid, rejected = row

                if status not in PERMITTED_LOAD_STATUSES:
                    raise ValueError(
                        f"Batch '{batch_id}' has ineligible status '{status}' for warehouse loading. "
                        f"Only batches with status in {PERMITTED_LOAD_STATUSES} can be loaded."
                    )
                if validated_at is None:
                    raise ValueError(f"Batch '{batch_id}' has not been validated (validated_at is NULL) and cannot be loaded.")

                # 2. Preflight Dependency Check: Ensure referenced historical dimensions exist
                self._preflight_dimension_checks(cur, batch_id)

                # 3. Ensure date dimension coverage for all valid transaction timestamps in the batch
                self._ensure_batch_dates_covered(cur, batch_id)

                # 4. Load Dimensions in relational order with whitespace normalization
                summary.branches_loaded = self._load_branches(cur, batch_id)
                summary.customers_loaded = self._load_customers(cur, batch_id)
                summary.accounts_loaded = self._load_accounts(cur, batch_id)

                # 5. Load Facts (idempotent, skips identical replays, flags conflicting replays)
                inserted, skipped, conflicting = self._load_facts(cur, batch_id)
                summary.records_inserted = inserted
                summary.records_skipped = skipped
                summary.conflicting_replays = conflicting

                # If conflicting replays occurred, update batch status to SUCCEEDED_WITH_REJECTIONS
                if conflicting > 0:
                    status = BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS

                summary.status = status

                # 6. Update batch metrics in monitoring.etl_batch_runs
                cur.execute("""
                    UPDATE monitoring.etl_batch_runs
                    SET records_inserted = %s,
                        records_skipped = %s,
                        status = %s,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE batch_id = %s;
                """, (summary.records_inserted, summary.records_skipped, summary.status, batch_id))

        # 7. Run count and value reconciliation audit
        recon_engine = ReconciliationEngine(self.conn)
        recon_report = recon_engine.reconcile_batch(batch_id)
        summary.reconciliation_status = "RECONCILED" if recon_report.is_reconciled else "UNRECONCILED"

        return summary

    def _preflight_dimension_checks(self, cur: psycopg2.extensions.cursor, batch_id: str) -> None:
        """
        Verify that all dimensions referenced by valid accounts and transactions
        exist in the warehouse or are present in the current batch.
        """
        # A. Check customer references for valid accounts in this batch
        cur.execute("""
            SELECT DISTINCT TRIM(sa.customer_id)
            FROM staging.stg_accounts sa
            WHERE sa.batch_id = %s
              AND sa.source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'ACCOUNT'
              )
              AND TRIM(sa.customer_id) NOT IN (
                  SELECT dc.customer_id FROM warehouse.dim_customer dc
                  UNION
                  SELECT TRIM(sc.customer_id) FROM staging.stg_customers sc
                  WHERE sc.batch_id = %s AND sc.source_row_id NOT IN (
                      SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'CUSTOMER'
                  )
              );
        """, (batch_id, batch_id))
        missing_customers = [r[0] for r in cur.fetchall()]
        if missing_customers:
            raise ValueError(
                f"Warehouse load preflight check failed for batch '{batch_id}': "
                f"Referenced customer(s) {sorted(missing_customers)} do not exist in warehouse.dim_customer or current batch. "
                f"Prerequisite batches containing these dimensions must be loaded into the warehouse first."
            )

        # B. Check branch references for valid accounts in this batch
        cur.execute("""
            SELECT DISTINCT TRIM(sa.branch_id)
            FROM staging.stg_accounts sa
            WHERE sa.batch_id = %s
              AND sa.source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'ACCOUNT'
              )
              AND TRIM(sa.branch_id) NOT IN (
                  SELECT db.branch_id FROM warehouse.dim_branch db
                  UNION
                  SELECT TRIM(sb.branch_id) FROM staging.stg_branches sb
                  WHERE sb.batch_id = %s AND sb.source_row_id NOT IN (
                      SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'BRANCH'
                  )
              );
        """, (batch_id, batch_id))
        missing_branches = [r[0] for r in cur.fetchall()]
        if missing_branches:
            raise ValueError(
                f"Warehouse load preflight check failed for batch '{batch_id}': "
                f"Referenced branch(es) {sorted(missing_branches)} do not exist in warehouse.dim_branch or current batch. "
                f"Prerequisite batches containing these dimensions must be loaded into the warehouse first."
            )

        # C. Check account references for valid transactions in this batch
        cur.execute("""
            SELECT DISTINCT TRIM(st.account_id)
            FROM staging.stg_transactions st
            WHERE st.batch_id = %s
              AND st.source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'TRANSACTION'
              )
              AND TRIM(st.account_id) NOT IN (
                  SELECT da.account_id FROM warehouse.dim_account da
                  UNION
                  SELECT TRIM(sa.account_id) FROM staging.stg_accounts sa
                  WHERE sa.batch_id = %s AND sa.source_row_id NOT IN (
                      SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'ACCOUNT'
                  )
              );
        """, (batch_id, batch_id))
        missing_accounts = [r[0] for r in cur.fetchall()]
        if missing_accounts:
            raise ValueError(
                f"Warehouse load preflight check failed for batch '{batch_id}': "
                f"Referenced account(s) {sorted(missing_accounts)} do not exist in warehouse.dim_account. "
                f"Prerequisite batches containing these dimensions must be loaded into the warehouse first."
            )

    def _ensure_batch_dates_covered(self, cur: psycopg2.extensions.cursor, batch_id: str) -> None:
        """Dynamically ensure dim_date covers all transaction dates in the batch."""
        cur.execute("""
            SELECT
                MIN((st.transaction_timestamp_raw::TIMESTAMPTZ AT TIME ZONE 'UTC')::DATE),
                MAX((st.transaction_timestamp_raw::TIMESTAMPTZ AT TIME ZONE 'UTC')::DATE)
            FROM staging.stg_transactions st
            WHERE st.batch_id = %s
              AND st.source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'TRANSACTION'
              );
        """, (batch_id,))
        row = cur.fetchone()
        if row and row[0] and row[1]:
            min_date, max_date = row
            cur.execute("""
                INSERT INTO warehouse.dim_date (
                    date_key, full_date, day_of_month, day_of_week, day_name,
                    week_of_year, month_number, month_name, quarter_number, year_number, is_weekend
                )
                SELECT
                    TO_CHAR(d, 'YYYYMMDD')::INT AS date_key,
                    d::DATE AS full_date,
                    EXTRACT(DAY FROM d)::INT AS day_of_month,
                    EXTRACT(ISODOW FROM d)::INT AS day_of_week,
                    TRIM(TO_CHAR(d, 'Day')) AS day_name,
                    EXTRACT(WEEK FROM d)::INT AS week_of_year,
                    EXTRACT(MONTH FROM d)::INT AS month_number,
                    TRIM(TO_CHAR(d, 'Month')) AS month_name,
                    EXTRACT(QUARTER FROM d)::INT AS quarter_number,
                    EXTRACT(YEAR FROM d)::INT AS year_number,
                    (EXTRACT(ISODOW FROM d) IN (6, 7)) AS is_weekend
                FROM generate_series(%s::DATE, %s::DATE, '1 day'::INTERVAL) d
                ON CONFLICT (date_key) DO NOTHING;
            """, (min_date, max_date))

    def _load_branches(self, cur: psycopg2.extensions.cursor, batch_id: str) -> int:
        cur.execute("""
            SELECT DISTINCT TRIM(branch_id), TRIM(branch_name), TRIM(region)
            FROM staging.stg_branches
            WHERE batch_id = %s
              AND branch_id IS NOT NULL AND TRIM(branch_id) != ''
              AND source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'BRANCH'
              )
            ORDER BY TRIM(branch_id);
        """, (batch_id,))
        rows = cur.fetchall()

        count = 0
        for b_id, b_name, reg in rows:
            cur.execute("""
                INSERT INTO warehouse.dim_branch (branch_id, branch_name, region)
                VALUES (%s, %s, %s)
                ON CONFLICT (branch_id) DO UPDATE SET
                    branch_name = EXCLUDED.branch_name,
                    region = EXCLUDED.region,
                    updated_at = CURRENT_TIMESTAMP;
            """, (b_id, b_name, reg))
            count += 1
        return count

    def _load_customers(self, cur: psycopg2.extensions.cursor, batch_id: str) -> int:
        cur.execute("""
            SELECT DISTINCT TRIM(customer_id), TRIM(customer_segment), TRIM(created_date_raw), TRIM(customer_status)
            FROM staging.stg_customers
            WHERE batch_id = %s
              AND customer_id IS NOT NULL AND TRIM(customer_id) != ''
              AND source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'CUSTOMER'
              )
            ORDER BY TRIM(customer_id);
        """, (batch_id,))
        rows = cur.fetchall()

        count = 0
        for c_id, seg, c_date_raw, stat in rows:
            cur.execute("""
                INSERT INTO warehouse.dim_customer (customer_id, customer_segment, customer_status, created_date)
                VALUES (%s, %s, %s, %s::DATE)
                ON CONFLICT (customer_id) DO UPDATE SET
                    customer_segment = EXCLUDED.customer_segment,
                    customer_status = EXCLUDED.customer_status,
                    created_date = EXCLUDED.created_date,
                    updated_at = CURRENT_TIMESTAMP;
            """, (c_id, seg, stat, c_date_raw))
            count += 1
        return count

    def _load_accounts(self, cur: psycopg2.extensions.cursor, batch_id: str) -> int:
        cur.execute("""
            SELECT DISTINCT
                TRIM(sa.account_id),
                dc.customer_key,
                db.branch_key,
                TRIM(sa.account_type),
                TRIM(sa.account_status),
                TRIM(sa.currency),
                TRIM(sa.opened_date_raw)
            FROM staging.stg_accounts sa
            JOIN warehouse.dim_customer dc ON TRIM(sa.customer_id) = dc.customer_id
            JOIN warehouse.dim_branch db ON TRIM(sa.branch_id) = db.branch_id
            WHERE sa.batch_id = %s
              AND sa.account_id IS NOT NULL AND TRIM(sa.account_id) != ''
              AND sa.source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'ACCOUNT'
              )
            ORDER BY TRIM(sa.account_id);
        """, (batch_id,))
        rows = cur.fetchall()

        count = 0
        for a_id, c_key, b_key, a_type, a_stat, curr, opened_raw in rows:
            cur.execute("""
                INSERT INTO warehouse.dim_account (
                    account_id, customer_key, branch_key, account_type, account_status, currency, opened_date
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::DATE)
                ON CONFLICT (account_id) DO UPDATE SET
                    customer_key = EXCLUDED.customer_key,
                    branch_key = EXCLUDED.branch_key,
                    account_type = EXCLUDED.account_type,
                    account_status = EXCLUDED.account_status,
                    currency = EXCLUDED.currency,
                    opened_date = EXCLUDED.opened_date,
                    updated_at = CURRENT_TIMESTAMP;
            """, (a_id, c_key, b_key, a_type, a_stat, curr, opened_raw))
            count += 1
        return count

    def _load_facts(self, cur: psycopg2.extensions.cursor, batch_id: str) -> Tuple[int, int, int]:
        cur.execute("""
            SELECT
                st.source_row_id,
                st.source_row_number,
                st.source_file,
                TRIM(st.transaction_id) AS transaction_id,
                COALESCE(NULLIF(TRIM(st.source_system), ''), 'CORE_BANKING') AS source_system,
                da.account_key,
                da.customer_key,
                da.branch_key,
                TO_CHAR(st.transaction_timestamp_raw::TIMESTAMPTZ AT TIME ZONE 'UTC', 'YYYYMMDD')::INT AS date_key,
                dtt.type_key,
                st.amount_raw::NUMERIC AS amount,
                TRIM(st.currency) AS currency,
                TRIM(st.status) AS status,
                TRIM(st.channel) AS channel,
                st.transaction_timestamp_raw::TIMESTAMPTZ AS transaction_timestamp,
                TRIM(st.account_id) AS account_id
            FROM staging.stg_transactions st
            JOIN warehouse.dim_account da ON TRIM(st.account_id) = da.account_id
            JOIN warehouse.dim_transaction_type dtt ON TRIM(st.transaction_type) = dtt.transaction_type_code
            WHERE st.batch_id = %s
              AND st.transaction_id IS NOT NULL AND TRIM(st.transaction_id) != ''
              AND st.source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'TRANSACTION'
              )
            ORDER BY st.source_row_number;
        """, (batch_id,))
        rows = cur.fetchall()

        inserted = 0
        skipped = 0
        conflicting = 0
        replay_issues: List[Tuple[str, str, str, int, int, str, str, str, str, str]] = []
        conflicting_quarantines: List[Tuple[str, str, str, int, int, str, str, int]] = []

        for row in rows:
            (
                row_id,
                row_num,
                file_name,
                clean_tid,
                clean_sys,
                acc_key,
                cust_key,
                br_key,
                date_key,
                type_key,
                amt,
                curr,
                stat,
                chan,
                ts,
                acc_id,
            ) = row

            # Check if this source event identity already exists in warehouse
            cur.execute("""
                SELECT ft.transaction_key, ft.amount, ft.currency, ft.status, da.account_id, ft.transaction_timestamp
                FROM warehouse.fact_transactions ft
                JOIN warehouse.dim_account da ON ft.account_key = da.account_key
                WHERE ft.source_system = %s AND ft.transaction_id = %s;
            """, (clean_sys, clean_tid))
            existing = cur.fetchone()

            if existing is not None:
                (
                    exist_key,
                    exist_amt,
                    exist_curr,
                    exist_stat,
                    exist_acc_id,
                    exist_ts,
                ) = existing

                # Compare existing warehouse fact payload with incoming staging row
                same_amount = (Decimal(str(exist_amt)) == Decimal(str(amt)))
                same_curr = (exist_curr.strip() == curr)
                same_status = (exist_stat.strip() == stat)
                same_acc = (exist_acc_id.strip() == acc_id)
                same_ts = (exist_ts == ts)

                if same_amount and same_curr and same_status and same_acc and same_ts:
                    # Identical replay: skip safely
                    skipped += 1
                    replay_issues.append((
                        uuid.uuid4().hex,
                        batch_id,
                        "TRANSACTION",
                        row_id,
                        row_num,
                        file_name,
                        RULE_SOURCE_REPLAY_SKIPPED,
                        SEVERITY_INFO,
                        f"Transaction event '{clean_tid}' in system '{clean_sys}' already loaded in warehouse; skipped under idempotency contract.",
                        DISPOSITION_SKIPPED,
                    ))
                else:
                    # Conflicting replay: payload mismatch for immutable event!
                    conflicting += 1
                    reason_msg = (
                        f"Conflicting replay: event '{clean_tid}' in system '{clean_sys}' already exists in warehouse with different payload "
                        f"(existing: amount={exist_amt} {exist_curr.strip()} status={exist_stat.strip()} account={exist_acc_id.strip()}; "
                        f"incoming: amount={amt} {curr} status={stat} account={acc_id})."
                    )
                    replay_issues.append((
                        uuid.uuid4().hex,
                        batch_id,
                        "TRANSACTION",
                        row_id,
                        row_num,
                        file_name,
                        RULE_CONFLICTING_REPLAY_PAYLOAD,
                        SEVERITY_ERROR,
                        reason_msg,
                        DISPOSITION_REJECTED,
                    ))
                    conflicting_quarantines.append((
                        uuid.uuid4().hex,
                        batch_id,
                        "TRANSACTION",
                        row_id,
                        row_num,
                        file_name,
                        RULE_CONFLICTING_REPLAY_PAYLOAD,
                        1,
                    ))
            else:
                # New event: insert into warehouse facts
                cur.execute("""
                    INSERT INTO warehouse.fact_transactions (
                        transaction_id, source_system, account_key, customer_key, branch_key,
                        date_key, type_key, amount, currency, status, channel,
                        transaction_timestamp, source_batch_id, source_row_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING transaction_key;
                """, (
                    clean_tid,
                    clean_sys,
                    acc_key,
                    cust_key,
                    br_key,
                    date_key,
                    type_key,
                    amt,
                    curr,
                    stat,
                    chan,
                    ts,
                    batch_id,
                    row_id,
                ))
                inserted += 1

        # Record replay and conflict issues in monitoring.data_quality_issues
        if replay_issues:
            insert_issue_sql = """
            INSERT INTO monitoring.data_quality_issues (
                issue_id, batch_id, entity_type, source_row_id, source_row_number,
                source_file, rule_code, severity, reason, disposition, detected_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
            """
            execute_batch(cur, insert_issue_sql, replay_issues)

        # Record conflicting replay rows in quarantine.quarantined_records
        if conflicting_quarantines:
            insert_q_sql = """
            INSERT INTO quarantine.quarantined_records (
                quarantine_id, batch_id, entity_type, source_row_id, source_row_number,
                source_file, primary_rule_code, issue_count, quarantined_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
            """
            execute_batch(cur, insert_q_sql, conflicting_quarantines)

            # Adjust batch accounting: transfer conflicting rows from valid to rejected
            cur.execute("""
                UPDATE monitoring.etl_batch_runs
                SET records_valid = records_valid - %s,
                    records_rejected = records_rejected + %s
                WHERE batch_id = %s;
            """, (conflicting, conflicting, batch_id))

        return inserted, skipped, conflicting
