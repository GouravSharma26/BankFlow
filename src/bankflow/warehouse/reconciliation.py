"""
Reconciliation Engine for BankFlow.
Performs count and value audit between staging, validation, and warehouse layers.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import psycopg2

from bankflow.constants import (
    BATCH_STATUS_FAILED,
    BATCH_STATUS_SUCCEEDED,
    BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS,
    RULE_CONFLICTING_REPLAY_PAYLOAD,
)
from bankflow.warehouse.models import ReconciliationReport


class ReconciliationEngine:
    """
    Reconciles batch records and monetary totals across ETL layers.
    Guarantees no records are lost or unaccounted for between staging and warehouse.
    """

    def __init__(self, conn: psycopg2.extensions.connection):
        self.conn = conn

    def reconcile_batch(self, batch_id: str) -> ReconciliationReport:
        """
        Perform count and value reconciliation for the specified batch.
        Updates reconciliation_status in monitoring.etl_batch_runs.
        """
        report = ReconciliationReport(batch_id=batch_id)
        discrepancies: List[str] = []

        with self.conn.cursor() as cur:
            # 1. Fetch batch run counts
            cur.execute("""
                SELECT records_extracted, records_staged, records_valid, records_rejected,
                       records_inserted, records_updated, records_skipped, status
                FROM monitoring.etl_batch_runs
                WHERE batch_id = %s;
            """, (batch_id,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Batch '{batch_id}' not found in monitoring.etl_batch_runs.")

            (
                rec_extracted,
                rec_staged,
                rec_valid,
                rec_rejected,
                rec_inserted,
                rec_updated,
                rec_skipped,
                batch_status,
            ) = row

            report.extracted_count = rec_extracted or 0
            report.staged_count = rec_staged or 0
            report.valid_count = rec_valid or 0
            report.rejected_count = rec_rejected or 0
            report.inserted_count = rec_inserted or 0
            report.skipped_count = rec_skipped or 0

            # 2. Quarantined records count check
            cur.execute("""
                SELECT count(*)
                FROM quarantine.quarantined_records
                WHERE batch_id = %s;
            """, (batch_id,))
            q_count = cur.fetchone()[0]
            report.quarantined_count = q_count

            # Count reconciliation rule 1: Staged = Valid + Rejected
            if report.staged_count != (report.valid_count + report.rejected_count):
                discrepancies.append(
                    f"Staging count mismatch: staged ({report.staged_count}) != "
                    f"valid ({report.valid_count}) + rejected ({report.rejected_count})."
                )

            # Count reconciliation rule 2: Quarantined records must equal records_rejected
            if report.quarantined_count != report.rejected_count:
                discrepancies.append(
                    f"Quarantine count mismatch: quarantined_records ({report.quarantined_count}) != "
                    f"records_rejected ({report.rejected_count})."
                )

            # 3. Transaction entity level count check
            cur.execute("""
                SELECT count(*)
                FROM staging.stg_transactions st
                WHERE st.batch_id = %s
                  AND st.source_row_id NOT IN (
                      SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'TRANSACTION'
                  );
            """, (batch_id,))
            valid_stg_txns = cur.fetchone()[0]

            # Fact count reconciliation: valid staging transactions = inserted + skipped
            if valid_stg_txns != (report.inserted_count + report.skipped_count):
                discrepancies.append(
                    f"Fact transaction count mismatch: valid staging transactions ({valid_stg_txns}) != "
                    f"inserted ({report.inserted_count}) + skipped ({report.skipped_count})."
                )

            # 4. Conflicting Replay Check: verify whether conflicting replays occurred
            cur.execute("""
                SELECT count(*)
                FROM monitoring.data_quality_issues
                WHERE batch_id = %s AND rule_code = %s;
            """, (batch_id, RULE_CONFLICTING_REPLAY_PAYLOAD))
            conflict_count = cur.fetchone()[0]
            if conflict_count > 0:
                discrepancies.append(
                    f"Batch contains {conflict_count} conflicting replay payload(s) where transaction event identity was reused with mismatched data."
                )

            # 5. Monetary Value Reconciliation (grouped by currency and status with whitespace normalization)
            # Only identical replays are excluded from the staging value sum
            cur.execute("""
                SELECT TRIM(st.currency), TRIM(st.status), COALESCE(SUM(st.amount_raw::NUMERIC), 0)
                FROM staging.stg_transactions st
                WHERE st.batch_id = %s
                  AND st.source_row_id NOT IN (
                      SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'TRANSACTION'
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM warehouse.fact_transactions ft
                      JOIN warehouse.dim_account da ON ft.account_key = da.account_key
                      JOIN warehouse.dim_transaction_type dtt ON ft.type_key = dtt.type_key
                      WHERE ft.source_system = COALESCE(NULLIF(TRIM(st.source_system), ''), 'CORE_BANKING')
                        AND ft.transaction_id = TRIM(st.transaction_id)
                        AND ft.source_batch_id != st.batch_id
                        AND ft.amount = st.amount_raw::NUMERIC
                        AND TRIM(ft.currency) = TRIM(st.currency)
                        AND TRIM(ft.status) = TRIM(st.status)
                        AND TRIM(da.account_id) = TRIM(st.account_id)
                        AND ft.transaction_timestamp = st.transaction_timestamp_raw::TIMESTAMPTZ
                        AND TRIM(dtt.transaction_type_code) = TRIM(st.transaction_type)
                        AND TRIM(ft.channel) = TRIM(st.channel)
                  )
                GROUP BY TRIM(st.currency), TRIM(st.status);
            """, (batch_id,))
            staging_values: Dict[Tuple[str, str], Decimal] = {
                (r[0].strip(), r[1].strip()): Decimal(str(r[2])) for r in cur.fetchall()
            }
            report.staging_value_by_currency_status = staging_values

            # Warehouse facts value for this batch
            cur.execute("""
                SELECT TRIM(ft.currency), TRIM(ft.status), COALESCE(SUM(ft.amount), 0)
                FROM warehouse.fact_transactions ft
                WHERE ft.source_batch_id = %s
                GROUP BY TRIM(ft.currency), TRIM(ft.status);
            """, (batch_id,))
            warehouse_values: Dict[Tuple[str, str], Decimal] = {
                (r[0].strip(), r[1].strip()): Decimal(str(r[2])) for r in cur.fetchall()
            }
            report.warehouse_value_by_currency_status = warehouse_values

            # Compare currency-status groups
            all_keys = set(staging_values.keys()) | set(warehouse_values.keys())
            for key in sorted(all_keys):
                stg_val = staging_values.get(key, Decimal("0.00"))
                wh_val = warehouse_values.get(key, Decimal("0.00"))
                if stg_val != wh_val:
                    discrepancies.append(
                        f"Monetary value mismatch for {key[0]} ({key[1]}): "
                        f"staging ({stg_val}) != warehouse ({wh_val})."
                    )

            report.discrepancies = discrepancies
            report.is_reconciled = (len(discrepancies) == 0)

            # 6. Persist reconciliation status in monitoring.etl_batch_runs
            status_str = "RECONCILED" if report.is_reconciled else "UNRECONCILED"
            cur.execute("""
                UPDATE monitoring.etl_batch_runs
                SET reconciliation_status = %s
                WHERE batch_id = %s;
            """, (status_str, batch_id))

        self.conn.commit()
        return report
