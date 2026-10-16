"""
Deterministic Data Quality Validation Engine.
Evaluates staged source records, assigns stable rule codes, persists quality issues,
and records quarantined rows while maintaining full lineage to raw staging data.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Set, Tuple

import psycopg2
from psycopg2.extras import execute_batch

from bankflow.constants import (
    BATCH_STATUS_FAILED,
    BATCH_STATUS_PENDING,
    BATCH_STATUS_RUNNING,
    BATCH_STATUS_SUCCEEDED,
    BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS,
    DISPOSITION_ACCEPTED,
    DISPOSITION_REJECTED,
    RULE_ACCOUNT_ID_DUPLICATE,
    RULE_ACCOUNT_ID_MISSING,
    RULE_ACCOUNT_NOT_FOUND,
    RULE_ACCOUNT_STATUS_UNSUPPORTED,
    RULE_ACCOUNT_TYPE_UNSUPPORTED,
    RULE_AMOUNT_MISSING,
    RULE_AMOUNT_PARSE_ERROR,
    RULE_AMOUNT_RULE_VIOLATION,
    RULE_BRANCH_ID_DUPLICATE,
    RULE_BRANCH_ID_MISSING,
    RULE_BRANCH_NAME_MISSING,
    RULE_BRANCH_NOT_FOUND,
    RULE_BRANCH_REGION_MISSING,
    RULE_CHANNEL_UNSUPPORTED,
    RULE_CURRENCY_MISMATCH,
    RULE_CURRENCY_MISSING,
    RULE_CURRENCY_UNSUPPORTED,
    RULE_CUSTOMER_ID_DUPLICATE,
    RULE_CUSTOMER_ID_MISSING,
    RULE_CUSTOMER_NOT_FOUND,
    RULE_CUSTOMER_SEGMENT_UNSUPPORTED,
    RULE_CUSTOMER_STATUS_UNSUPPORTED,
    RULE_DATE_PARSE_ERROR,
    RULE_SOURCE_SYSTEM_MISSING,
    RULE_STATUS_UNSUPPORTED,
    RULE_TIMESTAMP_PARSE_ERROR,
    RULE_TXN_ID_DUPLICATE,
    RULE_TXN_ID_MISSING,
    RULE_TYPE_UNSUPPORTED,
    SEVERITY_ERROR,
    SUPPORTED_ACCOUNT_STATUSES,
    SUPPORTED_ACCOUNT_TYPES,
    SUPPORTED_CHANNELS,
    SUPPORTED_CURRENCIES,
    SUPPORTED_CUSTOMER_SEGMENTS,
    SUPPORTED_CUSTOMER_STATUSES,
    SUPPORTED_TRANSACTION_STATUSES,
    SUPPORTED_TRANSACTION_TYPES,
)
from bankflow.db import transaction
from bankflow.validation.dates import parse_strict_date
from bankflow.validation.models import (
    BatchValidationSummary,
    RowValidationOutcome,
    ValidationIssue,
)
from bankflow.validation.schema import init_validation_schema


class ValidationEngine:
    """
    Validates staged records against domain rules and data contracts.
    Preserves raw staging data without in-place normalization or mutation.
    """

    def __init__(self, conn: psycopg2.extensions.connection):
        self.conn = conn

    def validate_batch(self, batch_id: str) -> BatchValidationSummary:
        """
        Validate all staged records for the given batch in relational reference order:
        branches -> customers -> accounts -> transactions.
        Idempotent: removes previous issues/quarantine records for this batch before re-evaluating.
        Updates batch counts, validated_at timestamp, and status in monitoring.etl_batch_runs.
        Protects batch lifecycle: rejects validation of FAILED, RUNNING, PENDING, or invalid batches,
        locking the batch row within the transaction so concurrent operations cannot bypass guards.
        """
        # Ensure schema exists
        init_validation_schema(self.conn)

        summary = BatchValidationSummary(batch_id=batch_id)
        all_issues: List[ValidationIssue] = []
        quarantine_rows: List[Tuple[str, str, str, int, int, str, str, int]] = []

        with transaction(self.conn):
            with self.conn.cursor() as cur:
                # 1. Lock and inspect batch lifecycle state within the transaction
                cur.execute("""
                    SELECT status, error_summary, records_staged, records_extracted, records_valid, records_rejected
                    FROM monitoring.etl_batch_runs
                    WHERE batch_id = %s
                    FOR UPDATE;
                """, (batch_id,))
                row = cur.fetchone()
                if not row:
                    raise ValueError(f"Batch with ID '{batch_id}' not found in monitoring.etl_batch_runs.")

                status, error_summary, rec_staged, rec_extracted, rec_valid, rec_rejected = row

                # Reject batches in FAILED, RUNNING, PENDING, or ineligible states
                if status == BATCH_STATUS_FAILED:
                    raise ValueError(
                        f"Batch '{batch_id}' is in FAILED status (reason: {error_summary or 'unspecified'}) and cannot be validated."
                    )
                if status == BATCH_STATUS_RUNNING:
                    raise ValueError(f"Batch '{batch_id}' is currently RUNNING and cannot be validated.")
                if status == BATCH_STATUS_PENDING:
                    raise ValueError(f"Batch '{batch_id}' is in PENDING status and cannot be validated.")
                if status not in (BATCH_STATUS_SUCCEEDED, BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS):
                    raise ValueError(f"Batch '{batch_id}' has ineligible status '{status}' for validation.")

                # 2. Clear previous issues and quarantine records for idempotency (safe for revalidation)
                cur.execute("DELETE FROM monitoring.data_quality_issues WHERE batch_id = %s;", (batch_id,))
                cur.execute("DELETE FROM quarantine.quarantined_records WHERE batch_id = %s;", (batch_id,))

                # 3. Validate Branches
                valid_branch_ids, branch_outcomes = self._validate_branches(cur, batch_id)

                # 4. Validate Customers
                valid_customer_ids, customer_outcomes = self._validate_customers(cur, batch_id)

                # 5. Validate Accounts (resolving against valid customers and branches)
                valid_accounts, account_outcomes = self._validate_accounts(
                    cur, batch_id, valid_customer_ids, valid_branch_ids
                )

                # 6. Validate Transactions (resolving against valid accounts and detecting batch duplicates)
                txn_outcomes = self._validate_transactions(cur, batch_id, valid_accounts)

                all_outcomes = branch_outcomes + customer_outcomes + account_outcomes + txn_outcomes
                summary.records_evaluated = len(all_outcomes)

                for outcome in all_outcomes:
                    # Accumulate issues
                    for issue in outcome.issues:
                        # Ensure disposition matches row's final outcome
                        issue.disposition = outcome.disposition
                        all_issues.append(issue)
                        summary.total_issues_count += 1
                        summary.issues_by_rule[issue.rule_code] = (
                            summary.issues_by_rule.get(issue.rule_code, 0) + 1
                        )
                        summary.issues_by_severity[issue.severity] = (
                            summary.issues_by_severity.get(issue.severity, 0) + 1
                        )

                    if outcome.is_rejected:
                        summary.records_rejected += 1
                        # Capture primary fatal rule code
                        primary_code = next(
                            (i.rule_code for i in outcome.issues if i.severity == SEVERITY_ERROR),
                            "UNKNOWN_ERROR",
                        )
                        first_issue = outcome.issues[0]
                        quarantine_rows.append((
                            uuid.uuid4().hex,
                            batch_id,
                            outcome.entity_type,
                            outcome.source_row_id,
                            outcome.source_row_number,
                            first_issue.source_file,
                            primary_code,
                            len(outcome.issues),
                        ))
                    elif outcome.has_warnings:
                        summary.records_valid += 1
                        summary.records_warned += 1
                    else:
                        summary.records_valid += 1

                # 7. Bulk insert issues
                if all_issues:
                    issue_tuples = [i.to_db_tuple() for i in all_issues]
                    insert_issue_sql = """
                    INSERT INTO monitoring.data_quality_issues (
                        issue_id, batch_id, entity_type, source_row_id, source_row_number,
                        source_file, rule_code, severity, reason, disposition, detected_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    execute_batch(cur, insert_issue_sql, issue_tuples)

                # 8. Bulk insert quarantine records
                if quarantine_rows:
                    insert_quarantine_sql = """
                    INSERT INTO quarantine.quarantined_records (
                        quarantine_id, batch_id, entity_type, source_row_id,
                        source_row_number, source_file, primary_rule_code, issue_count
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    execute_batch(cur, insert_quarantine_sql, quarantine_rows)

                # 9. Determine batch final status and update monitoring.etl_batch_runs with validated_at
                if summary.records_rejected > 0:
                    summary.batch_status = BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS
                else:
                    summary.batch_status = BATCH_STATUS_SUCCEEDED

                cur.execute("""
                    UPDATE monitoring.etl_batch_runs
                    SET status = %s,
                        records_valid = %s,
                        records_rejected = %s,
                        validated_at = CURRENT_TIMESTAMP
                    WHERE batch_id = %s;
                """, (summary.batch_status, summary.records_valid, summary.records_rejected, batch_id))

        return summary

    def _validate_branches(
        self, cur: psycopg2.extensions.cursor, batch_id: str
    ) -> Tuple[Set[str], List[RowValidationOutcome]]:
        cur.execute("""
            SELECT source_row_id, source_row_number, source_file, branch_id, branch_name, region
            FROM staging.stg_branches
            WHERE batch_id = %s
            ORDER BY source_row_number;
        """, (batch_id,))
        rows = cur.fetchall()

        # Pre-scan for duplicate branch IDs in this batch
        raw_b_ids = [(r[3] or "").strip() for r in rows if (r[3] or "").strip()]
        b_counts = Counter(raw_b_ids)
        duplicate_b_ids: Set[str] = {bid for bid, count in b_counts.items() if count > 1}

        valid_ids: Set[str] = set()
        outcomes: List[RowValidationOutcome] = []

        for row in rows:
            row_id, row_num, file_name, b_id, b_name, region = row
            outcome = RowValidationOutcome(source_row_id=row_id, source_row_number=row_num, entity_type="BRANCH")

            clean_id = (b_id or "").strip()
            if not clean_id:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="BRANCH",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_BRANCH_ID_MISSING,
                    severity=SEVERITY_ERROR,
                    reason="Branch ID is missing or empty.",
                ))
            elif clean_id in duplicate_b_ids:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="BRANCH",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_BRANCH_ID_DUPLICATE,
                    severity=SEVERITY_ERROR,
                    reason=f"Duplicate branch ID '{clean_id}' detected within batch.",
                ))

            clean_name = (b_name or "").strip()
            if not clean_name:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="BRANCH",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_BRANCH_NAME_MISSING,
                    severity=SEVERITY_ERROR,
                    reason="Branch name is missing or empty.",
                ))

            clean_region = (region or "").strip()
            if not clean_region:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="BRANCH",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_BRANCH_REGION_MISSING,
                    severity=SEVERITY_ERROR,
                    reason="Branch region is missing or empty.",
                ))

            if not outcome.is_rejected and clean_id:
                valid_ids.add(clean_id)

            outcomes.append(outcome)

        # Include previously validated branches from completed batches only (not quarantined)
        cur.execute("""
            SELECT DISTINCT sb.branch_id
            FROM staging.stg_branches sb
            JOIN monitoring.etl_batch_runs b ON sb.batch_id = b.batch_id
            WHERE sb.batch_id != %s
              AND b.validated_at IS NOT NULL
              AND b.status IN ('SUCCEEDED', 'SUCCEEDED_WITH_REJECTIONS')
              AND (b.records_valid + b.records_rejected) = b.records_staged
              AND b.records_staged > 0
              AND sb.branch_id IS NOT NULL AND TRIM(sb.branch_id) != ''
              AND sb.source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'BRANCH'
              );
        """, (batch_id,))
        for (prev_id,) in cur.fetchall():
            if prev_id and prev_id.strip():
                clean_prev_id = prev_id.strip()
                if clean_prev_id not in duplicate_b_ids:
                    valid_ids.add(clean_prev_id)

        return valid_ids, outcomes


    def _validate_customers(
        self, cur: psycopg2.extensions.cursor, batch_id: str
    ) -> Tuple[Set[str], List[RowValidationOutcome]]:
        cur.execute("""
            SELECT source_row_id, source_row_number, source_file,
                   customer_id, customer_segment, created_date_raw, customer_status
            FROM staging.stg_customers
            WHERE batch_id = %s
            ORDER BY source_row_number;
        """, (batch_id,))
        rows = cur.fetchall()

        # Pre-scan for duplicate customer IDs in this batch
        raw_c_ids = [(r[3] or "").strip() for r in rows if (r[3] or "").strip()]
        c_counts = Counter(raw_c_ids)
        duplicate_c_ids: Set[str] = {cid for cid, count in c_counts.items() if count > 1}

        valid_ids: Set[str] = set()
        outcomes: List[RowValidationOutcome] = []

        for row in rows:
            row_id, row_num, file_name, c_id, segment, created_date, status = row
            outcome = RowValidationOutcome(source_row_id=row_id, source_row_number=row_num, entity_type="CUSTOMER")

            clean_id = (c_id or "").strip()
            if not clean_id:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="CUSTOMER",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_CUSTOMER_ID_MISSING,
                    severity=SEVERITY_ERROR,
                    reason="Customer ID is missing or empty.",
                ))
            elif clean_id in duplicate_c_ids:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="CUSTOMER",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_CUSTOMER_ID_DUPLICATE,
                    severity=SEVERITY_ERROR,
                    reason=f"Duplicate customer ID '{clean_id}' detected within batch.",
                ))

            clean_segment = (segment or "").strip()
            if clean_segment not in SUPPORTED_CUSTOMER_SEGMENTS:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="CUSTOMER",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_CUSTOMER_SEGMENT_UNSUPPORTED,
                    severity=SEVERITY_ERROR,
                    reason=f"Customer segment '{segment}' is unsupported. Allowed: {sorted(SUPPORTED_CUSTOMER_SEGMENTS)}",
                ))

            date_res = parse_strict_date(created_date)
            if not date_res.is_valid:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="CUSTOMER",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_DATE_PARSE_ERROR,
                    severity=SEVERITY_ERROR,
                    reason=f"Customer created_date '{created_date}': {date_res.error_message}",
                ))

            clean_status = (status or "").strip()
            if clean_status not in SUPPORTED_CUSTOMER_STATUSES:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="CUSTOMER",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_CUSTOMER_STATUS_UNSUPPORTED,
                    severity=SEVERITY_ERROR,
                    reason=f"Customer status '{status}' is unsupported. Allowed: {sorted(SUPPORTED_CUSTOMER_STATUSES)}",
                ))

            if not outcome.is_rejected and clean_id:
                valid_ids.add(clean_id)

            outcomes.append(outcome)

        # Include previously validated customers from completed batches only (not quarantined)
        cur.execute("""
            SELECT DISTINCT sc.customer_id
            FROM staging.stg_customers sc
            JOIN monitoring.etl_batch_runs b ON sc.batch_id = b.batch_id
            WHERE sc.batch_id != %s
              AND b.validated_at IS NOT NULL
              AND b.status IN ('SUCCEEDED', 'SUCCEEDED_WITH_REJECTIONS')
              AND (b.records_valid + b.records_rejected) = b.records_staged
              AND b.records_staged > 0
              AND sc.customer_id IS NOT NULL AND TRIM(sc.customer_id) != ''
              AND sc.source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'CUSTOMER'
              );
        """, (batch_id,))
        for (prev_id,) in cur.fetchall():
            if prev_id and prev_id.strip():
                clean_prev_id = prev_id.strip()
                if clean_prev_id not in duplicate_c_ids:
                    valid_ids.add(clean_prev_id)

        return valid_ids, outcomes


    def _validate_accounts(
        self,
        cur: psycopg2.extensions.cursor,
        batch_id: str,
        valid_customer_ids: Set[str],
        valid_branch_ids: Set[str],
    ) -> Tuple[Dict[str, str], List[RowValidationOutcome]]:
        cur.execute("""
            SELECT source_row_id, source_row_number, source_file,
                   account_id, customer_id, branch_id, account_type, account_status,
                   opened_date_raw, currency
            FROM staging.stg_accounts
            WHERE batch_id = %s
            ORDER BY source_row_number;
        """, (batch_id,))
        rows = cur.fetchall()

        # Pre-scan for duplicate account IDs in this batch
        raw_a_ids = [(r[3] or "").strip() for r in rows if (r[3] or "").strip()]
        a_counts = Counter(raw_a_ids)
        duplicate_a_ids: Set[str] = {aid for aid, count in a_counts.items() if count > 1}

        valid_accounts: Dict[str, str] = {}
        outcomes: List[RowValidationOutcome] = []

        for row in rows:
            row_id, row_num, file_name, a_id, c_id, b_id, a_type, a_status, opened_dt, curr = row
            outcome = RowValidationOutcome(source_row_id=row_id, source_row_number=row_num, entity_type="ACCOUNT")

            clean_id = (a_id or "").strip()
            if not clean_id:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="ACCOUNT",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_ACCOUNT_ID_MISSING,
                    severity=SEVERITY_ERROR,
                    reason="Account ID is missing or empty.",
                ))
            elif clean_id in duplicate_a_ids:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="ACCOUNT",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_ACCOUNT_ID_DUPLICATE,
                    severity=SEVERITY_ERROR,
                    reason=f"Duplicate account ID '{clean_id}' detected within batch.",
                ))

            # Customer reference check
            clean_cid = (c_id or "").strip()
            if not clean_cid or clean_cid not in valid_customer_ids:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="ACCOUNT",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_CUSTOMER_NOT_FOUND,
                    severity=SEVERITY_ERROR,
                    reason=f"Customer reference '{c_id}' could not be resolved.",
                ))

            # Branch reference check
            clean_bid = (b_id or "").strip()
            if not clean_bid or clean_bid not in valid_branch_ids:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="ACCOUNT",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_BRANCH_NOT_FOUND,
                    severity=SEVERITY_ERROR,
                    reason=f"Branch reference '{b_id}' could not be resolved.",
                ))

            # Opened date check
            date_res = parse_strict_date(opened_dt)
            if not date_res.is_valid:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="ACCOUNT",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_DATE_PARSE_ERROR,
                    severity=SEVERITY_ERROR,
                    reason=f"Account opened_date '{opened_dt}': {date_res.error_message}",
                ))

            # Account type check
            clean_type = (a_type or "").strip()
            if clean_type not in SUPPORTED_ACCOUNT_TYPES:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="ACCOUNT",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_ACCOUNT_TYPE_UNSUPPORTED,
                    severity=SEVERITY_ERROR,
                    reason=f"Account type '{a_type}' is unsupported. Allowed: {sorted(SUPPORTED_ACCOUNT_TYPES)}",
                ))

            # Account status check
            clean_status = (a_status or "").strip()
            if clean_status not in SUPPORTED_ACCOUNT_STATUSES:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="ACCOUNT",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_ACCOUNT_STATUS_UNSUPPORTED,
                    severity=SEVERITY_ERROR,
                    reason=f"Account status '{a_status}' is unsupported. Allowed: {sorted(SUPPORTED_ACCOUNT_STATUSES)}",
                ))

            # Currency check
            clean_curr = (curr or "").strip()
            if not clean_curr:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="ACCOUNT",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_CURRENCY_MISSING,
                    severity=SEVERITY_ERROR,
                    reason="Account currency is missing or empty.",
                ))
            elif clean_curr not in SUPPORTED_CURRENCIES:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="ACCOUNT",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_CURRENCY_UNSUPPORTED,
                    severity=SEVERITY_ERROR,
                    reason=f"Account currency '{curr}' is unsupported. Allowed: {sorted(SUPPORTED_CURRENCIES)}",
                ))

            if not outcome.is_rejected and clean_id and clean_curr in SUPPORTED_CURRENCIES:
                valid_accounts[clean_id] = clean_curr

            outcomes.append(outcome)

        # Include previously validated accounts from completed batches only (not quarantined)
        cur.execute("""
            SELECT DISTINCT sa.account_id, sa.currency
            FROM staging.stg_accounts sa
            JOIN monitoring.etl_batch_runs b ON sa.batch_id = b.batch_id
            WHERE sa.batch_id != %s
              AND b.validated_at IS NOT NULL
              AND b.status IN ('SUCCEEDED', 'SUCCEEDED_WITH_REJECTIONS')
              AND (b.records_valid + b.records_rejected) = b.records_staged
              AND b.records_staged > 0
              AND sa.account_id IS NOT NULL AND TRIM(sa.account_id) != ''
              AND sa.source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'ACCOUNT'
              );
        """, (batch_id,))
        for prev_id, prev_curr in cur.fetchall():
            if prev_id and prev_id.strip() and prev_curr:
                clean_prev_id = prev_id.strip()
                if clean_prev_id not in duplicate_a_ids and clean_prev_id not in valid_accounts:
                    valid_accounts[clean_prev_id] = prev_curr.strip()

        return valid_accounts, outcomes

    def _validate_transactions(
        self,
        cur: psycopg2.extensions.cursor,
        batch_id: str,
        valid_accounts: Dict[str, str],
    ) -> List[RowValidationOutcome]:
        cur.execute("""
            SELECT source_row_id, source_row_number, source_file,
                   transaction_id, account_id, transaction_type, amount_raw, currency,
                   transaction_timestamp_raw, status, channel, counterparty_account_id,
                   source_system, raw_payload
            FROM staging.stg_transactions
            WHERE batch_id = %s
            ORDER BY source_row_number;
        """, (batch_id,))
        rows = cur.fetchall()

        # Pre-scan for duplicate transaction IDs within this batch (ignoring empty strings)
        raw_txn_ids = [(r[3] or "").strip() for r in rows if (r[3] or "").strip()]
        id_counts = Counter(raw_txn_ids)
        duplicate_txn_ids: Set[str] = {tid for tid, count in id_counts.items() if count > 1}

        outcomes: List[RowValidationOutcome] = []

        for row in rows:
            (
                row_id,
                row_num,
                file_name,
                t_id,
                a_id,
                t_type,
                amt_raw,
                curr,
                ts_raw,
                status,
                channel,
                cp_account_id,
                src_sys,
                raw_payload,
            ) = row

            outcome = RowValidationOutcome(source_row_id=row_id, source_row_number=row_num, entity_type="TRANSACTION")

            # 1. Transaction ID check
            clean_tid = (t_id or "").strip()
            if not clean_tid:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="TRANSACTION",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_TXN_ID_MISSING,
                    severity=SEVERITY_ERROR,
                    reason="Transaction ID is missing or empty.",
                ))
            elif clean_tid in duplicate_txn_ids:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="TRANSACTION",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_TXN_ID_DUPLICATE,
                    severity=SEVERITY_ERROR,
                    reason=f"Duplicate transaction ID '{clean_tid}' detected within batch.",
                ))

            # 2. Account reference check and currency consistency
            clean_aid = (a_id or "").strip()
            clean_curr = (curr or "").strip()

            if not clean_aid:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="TRANSACTION",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_ACCOUNT_ID_MISSING,
                    severity=SEVERITY_ERROR,
                    reason="Account ID is missing or empty.",
                ))
            elif clean_aid not in valid_accounts:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="TRANSACTION",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_ACCOUNT_NOT_FOUND,
                    severity=SEVERITY_ERROR,
                    reason=f"Account reference '{a_id}' could not be resolved.",
                ))
            else:
                # Account resolved! Check currency consistency between transaction and account
                expected_curr = valid_accounts[clean_aid]
                if clean_curr and clean_curr in SUPPORTED_CURRENCIES and clean_curr != expected_curr:
                    outcome.issues.append(ValidationIssue(
                        batch_id=batch_id,
                        entity_type="TRANSACTION",
                        source_file=file_name,
                        source_row_number=row_num,
                        source_row_id=row_id,
                        rule_code=RULE_CURRENCY_MISMATCH,
                        severity=SEVERITY_ERROR,
                        reason=f"Transaction currency '{curr}' does not match account currency '{expected_curr}' for account '{clean_aid}'.",
                    ))

            # 3. Source system check
            clean_src_sys = (src_sys or "").strip()
            if not clean_src_sys:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="TRANSACTION",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_SOURCE_SYSTEM_MISSING,
                    severity=SEVERITY_ERROR,
                    reason="Transaction source_system is missing or empty.",
                ))

            # 4. Transaction Type check
            clean_type = (t_type or "").strip()
            if clean_type not in SUPPORTED_TRANSACTION_TYPES:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="TRANSACTION",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_TYPE_UNSUPPORTED,
                    severity=SEVERITY_ERROR,
                    reason=f"Transaction type '{t_type}' is unsupported. Allowed: {sorted(SUPPORTED_TRANSACTION_TYPES)}",
                ))

            # 5. Amount check (Decimal parsing and type-specific rules)
            clean_amt = (amt_raw or "").strip()
            if not clean_amt:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="TRANSACTION",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_AMOUNT_MISSING,
                    severity=SEVERITY_ERROR,
                    reason="Amount is missing or empty.",
                ))
            else:
                try:
                    parsed_decimal = Decimal(clean_amt)
                    if not parsed_decimal.is_finite():
                        outcome.issues.append(ValidationIssue(
                            batch_id=batch_id,
                            entity_type="TRANSACTION",
                            source_file=file_name,
                            source_row_number=row_num,
                            source_row_id=row_id,
                            rule_code=RULE_AMOUNT_PARSE_ERROR,
                            severity=SEVERITY_ERROR,
                            reason=f"Amount '{amt_raw}' is not a finite numeric decimal.",
                        ))
                    elif parsed_decimal <= Decimal("0.00"):
                        outcome.issues.append(ValidationIssue(
                            batch_id=batch_id,
                            entity_type="TRANSACTION",
                            source_file=file_name,
                            source_row_number=row_num,
                            source_row_id=row_id,
                            rule_code=RULE_AMOUNT_RULE_VIOLATION,
                            severity=SEVERITY_ERROR,
                            reason=f"Amount {parsed_decimal} must be strictly greater than 0.00.",
                        ))
                except (InvalidOperation, ValueError):
                    outcome.issues.append(ValidationIssue(
                        batch_id=batch_id,
                        entity_type="TRANSACTION",
                        source_file=file_name,
                        source_row_number=row_num,
                        source_row_id=row_id,
                        rule_code=RULE_AMOUNT_PARSE_ERROR,
                        severity=SEVERITY_ERROR,
                        reason=f"Amount '{amt_raw}' cannot be parsed as a numeric decimal.",
                    ))

            # 6. Currency check
            if not clean_curr:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="TRANSACTION",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_CURRENCY_MISSING,
                    severity=SEVERITY_ERROR,
                    reason="Currency is missing or empty.",
                ))
            elif clean_curr not in SUPPORTED_CURRENCIES:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="TRANSACTION",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_CURRENCY_UNSUPPORTED,
                    severity=SEVERITY_ERROR,
                    reason=f"Currency '{curr}' is unsupported. Allowed: {sorted(SUPPORTED_CURRENCIES)}",
                ))

            # 7. Timestamp check (Timezone-aware parsing; past/late timestamps are valid)
            clean_ts = (ts_raw or "").strip()
            if not clean_ts:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="TRANSACTION",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_TIMESTAMP_PARSE_ERROR,
                    severity=SEVERITY_ERROR,
                    reason="Transaction timestamp is missing or empty.",
                ))
            else:
                try:
                    # Accepts ISO 8601 strings (e.g. 2026-01-01T12:00:00+00:00, 2026-01-01T12:00:00Z)
                    parsed_dt = datetime.fromisoformat(clean_ts.replace("Z", "+00:00"))
                    if parsed_dt.tzinfo is None:
                        outcome.issues.append(ValidationIssue(
                            batch_id=batch_id,
                            entity_type="TRANSACTION",
                            source_file=file_name,
                            source_row_number=row_num,
                            source_row_id=row_id,
                            rule_code=RULE_TIMESTAMP_PARSE_ERROR,
                            severity=SEVERITY_ERROR,
                            reason=f"Timestamp '{ts_raw}' lacks explicit timezone offset.",
                        ))
                except Exception:
                    outcome.issues.append(ValidationIssue(
                        batch_id=batch_id,
                        entity_type="TRANSACTION",
                        source_file=file_name,
                        source_row_number=row_num,
                        source_row_id=row_id,
                        rule_code=RULE_TIMESTAMP_PARSE_ERROR,
                        severity=SEVERITY_ERROR,
                        reason=f"Timestamp '{ts_raw}' cannot be parsed as a valid ISO 8601 datetime.",
                    ))

            # 8. Status check
            clean_status = (status or "").strip()
            if clean_status not in SUPPORTED_TRANSACTION_STATUSES:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="TRANSACTION",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_STATUS_UNSUPPORTED,
                    severity=SEVERITY_ERROR,
                    reason=f"Status '{status}' is unsupported. Allowed: {sorted(SUPPORTED_TRANSACTION_STATUSES)}",
                ))

            # 9. Channel check
            clean_channel = (channel or "").strip()
            if clean_channel not in SUPPORTED_CHANNELS:
                outcome.issues.append(ValidationIssue(
                    batch_id=batch_id,
                    entity_type="TRANSACTION",
                    source_file=file_name,
                    source_row_number=row_num,
                    source_row_id=row_id,
                    rule_code=RULE_CHANNEL_UNSUPPORTED,
                    severity=SEVERITY_ERROR,
                    reason=f"Channel '{channel}' is unsupported. Allowed: {sorted(SUPPORTED_CHANNELS)}",
                ))

            outcomes.append(outcome)

        return outcomes
