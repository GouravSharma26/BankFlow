"""
Warehouse Loading Engine.
Loads conformed dimensions and transaction facts from staging to PostgreSQL warehouse.
Enforces database-level idempotency, transactional consistency, and reconciliation audit.
"""

from __future__ import annotations

import uuid
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
    DISPOSITION_SKIPPED,
    RULE_SOURCE_REPLAY_SKIPPED,
    SEVERITY_INFO,
)
from bankflow.db import transaction
from bankflow.warehouse.models import WarehouseLoadingSummary
from bankflow.warehouse.reconciliation import ReconciliationEngine
from bankflow.warehouse.schema import init_warehouse_schema


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
                # 1. Lock and verify batch lifecycle eligibility
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

                if status == BATCH_STATUS_FAILED:
                    raise ValueError(f"Batch '{batch_id}' is in FAILED status and cannot be loaded into the warehouse.")
                if status in (BATCH_STATUS_PENDING, BATCH_STATUS_RUNNING):
                    raise ValueError(f"Batch '{batch_id}' has not completed staging/validation (status: {status}).")
                if validated_at is None:
                    raise ValueError(f"Batch '{batch_id}' has not been validated and cannot be loaded.")

                # 2. Load Dimensions in relational order
                summary.branches_loaded = self._load_branches(cur, batch_id)
                summary.customers_loaded = self._load_customers(cur, batch_id)
                summary.accounts_loaded = self._load_accounts(cur, batch_id)

                # 3. Load Facts (idempotent, skips already loaded events)
                inserted, skipped = self._load_facts(cur, batch_id)
                summary.records_inserted = inserted
                summary.records_skipped = skipped
                summary.status = status

                # 4. Update batch metrics in monitoring.etl_batch_runs
                cur.execute("""
                    UPDATE monitoring.etl_batch_runs
                    SET records_inserted = %s,
                        records_skipped = %s,
                        completed_at = CURRENT_TIMESTAMP
                    WHERE batch_id = %s;
                """, (summary.records_inserted, summary.records_skipped, batch_id))

        # 5. Run count and value reconciliation audit
        recon_engine = ReconciliationEngine(self.conn)
        recon_report = recon_engine.reconcile_batch(batch_id)
        summary.reconciliation_status = "RECONCILED" if recon_report.is_reconciled else "UNRECONCILED"

        return summary

    def _load_branches(self, cur: psycopg2.extensions.cursor, batch_id: str) -> int:
        cur.execute("""
            SELECT DISTINCT branch_id, branch_name, region
            FROM staging.stg_branches
            WHERE batch_id = %s
              AND branch_id IS NOT NULL AND TRIM(branch_id) != ''
              AND source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'BRANCH'
              )
            ORDER BY branch_id;
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
            """, (b_id.strip(), b_name.strip(), reg.strip()))
            count += 1
        return count

    def _load_customers(self, cur: psycopg2.extensions.cursor, batch_id: str) -> int:
        cur.execute("""
            SELECT DISTINCT customer_id, customer_segment, created_date_raw, customer_status
            FROM staging.stg_customers
            WHERE batch_id = %s
              AND customer_id IS NOT NULL AND TRIM(customer_id) != ''
              AND source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'CUSTOMER'
              )
            ORDER BY customer_id;
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
            """, (c_id.strip(), seg.strip(), stat.strip(), c_date_raw.strip()))
            count += 1
        return count

    def _load_accounts(self, cur: psycopg2.extensions.cursor, batch_id: str) -> int:
        cur.execute("""
            SELECT DISTINCT
                sa.account_id,
                dc.customer_key,
                db.branch_key,
                sa.account_type,
                sa.account_status,
                sa.currency,
                sa.opened_date_raw
            FROM staging.stg_accounts sa
            JOIN warehouse.dim_customer dc ON sa.customer_id = dc.customer_id
            JOIN warehouse.dim_branch db ON sa.branch_id = db.branch_id
            WHERE sa.batch_id = %s
              AND sa.account_id IS NOT NULL AND TRIM(sa.account_id) != ''
              AND sa.source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'ACCOUNT'
              )
            ORDER BY sa.account_id;
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
            """, (a_id.strip(), c_key, b_key, a_type.strip(), a_stat.strip(), curr.strip(), opened_raw.strip()))
            count += 1
        return count

    def _load_facts(self, cur: psycopg2.extensions.cursor, batch_id: str) -> Tuple[int, int]:
        cur.execute("""
            SELECT
                st.source_row_id,
                st.source_row_number,
                st.source_file,
                st.transaction_id,
                st.source_system,
                da.account_key,
                da.customer_key,
                da.branch_key,
                TO_CHAR(st.transaction_timestamp_raw::TIMESTAMPTZ AT TIME ZONE 'UTC', 'YYYYMMDD')::INT AS date_key,
                dtt.type_key,
                st.amount_raw::NUMERIC AS amount,
                st.currency,
                st.status,
                st.channel,
                st.transaction_timestamp_raw::TIMESTAMPTZ AS transaction_timestamp
            FROM staging.stg_transactions st
            JOIN warehouse.dim_account da ON st.account_id = da.account_id
            JOIN warehouse.dim_transaction_type dtt ON st.transaction_type = dtt.transaction_type_code
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
        replay_issues: List[Tuple[str, str, str, int, int, str, str, str, str, str]] = []

        for row in rows:
            (
                row_id,
                row_num,
                file_name,
                t_id,
                src_sys,
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
            ) = row

            clean_tid = t_id.strip()
            clean_sys = (src_sys or "CORE").strip()

            cur.execute("""
                INSERT INTO warehouse.fact_transactions (
                    transaction_id, source_system, account_key, customer_key, branch_key,
                    date_key, type_key, amount, currency, status, channel,
                    transaction_timestamp, source_batch_id, source_row_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_system, transaction_id) DO NOTHING
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
                curr.strip(),
                stat.strip(),
                chan.strip(),
                ts,
                batch_id,
                row_id,
            ))
            res = cur.fetchone()

            if res is not None:
                inserted += 1
            else:
                # Replay / already loaded in warehouse under idempotency contract
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

        # Record replay skipped issues in monitoring.data_quality_issues
        if replay_issues:
            insert_issue_sql = """
            INSERT INTO monitoring.data_quality_issues (
                issue_id, batch_id, entity_type, source_row_id, source_row_number,
                source_file, rule_code, severity, reason, disposition, detected_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
            """
            execute_batch(cur, insert_issue_sql, replay_issues)

        return inserted, skipped
