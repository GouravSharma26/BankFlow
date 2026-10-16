"""
Deterministic Data Quality Validation Engine.
Evaluates staged source records, assigns stable rule codes, persists quality issues,
and records quarantined rows while maintaining full lineage to raw staging data.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Set, Tuple

import psycopg2
from psycopg2.extras import execute_batch

from bankflow.constants import (
    BATCH_STATUS_SUCCEEDED,
    BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS,
    DISPOSITION_ACCEPTED,
    DISPOSITION_REJECTED,
    RULE_ACCOUNT_ID_MISSING,
    RULE_ACCOUNT_NOT_FOUND,
    RULE_ACCOUNT_STATUS_UNSUPPORTED,
    RULE_ACCOUNT_TYPE_UNSUPPORTED,
    RULE_AMOUNT_MISSING,
    RULE_AMOUNT_PARSE_ERROR,
    RULE_AMOUNT_RULE_VIOLATION,
    RULE_BRANCH_ID_MISSING,
    RULE_BRANCH_NOT_FOUND,
    RULE_CHANNEL_UNSUPPORTED,
    RULE_CURRENCY_MISSING,
    RULE_CURRENCY_UNSUPPORTED,
    RULE_CUSTOMER_ID_MISSING,
    RULE_CUSTOMER_NOT_FOUND,
    RULE_CUSTOMER_SEGMENT_UNSUPPORTED,
    RULE_CUSTOMER_STATUS_UNSUPPORTED,
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
        Updates batch counts and status in monitoring.etl_batch_runs.
        """
        # Ensure schema exists
        init_validation_schema(self.conn)

        # Verify batch exists
        with self.conn.cursor() as cur:
            cur.execute("SELECT batch_id FROM monitoring.etl_batch_runs WHERE batch_id = %s;", (batch_id,))
            if not cur.fetchone():
                raise ValueError(f"Batch with ID '{batch_id}' not found in monitoring.etl_batch_runs.")

        summary = BatchValidationSummary(batch_id=batch_id)
        all_issues: List[ValidationIssue] = []
        quarantine_rows: List[Tuple[str, str, str, int, int, str, str, int]] = []

        with transaction(self.conn):
            with self.conn.cursor() as cur:
                # 1. Clear previous issues and quarantine records for idempotency
                cur.execute("DELETE FROM monitoring.data_quality_issues WHERE batch_id = %s;", (batch_id,))
                cur.execute("DELETE FROM quarantine.quarantined_records WHERE batch_id = %s;", (batch_id,))

                # 2. Validate Branches
                valid_branch_ids, branch_outcomes = self._validate_branches(cur, batch_id)

                # 3. Validate Customers
                valid_customer_ids, customer_outcomes = self._validate_customers(cur, batch_id)

                # 4. Validate Accounts (resolving against valid customers and branches)
                valid_account_ids, account_outcomes = self._validate_accounts(
                    cur, batch_id, valid_customer_ids, valid_branch_ids
                )

                # 5. Validate Transactions (resolving against valid accounts and detecting batch duplicates)
                txn_outcomes = self._validate_transactions(cur, batch_id, valid_account_ids)

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

                # 6. Bulk insert issues
                if all_issues:
                    issue_tuples = [i.to_db_tuple() for i in all_issues]
                    insert_issue_sql = """
                    INSERT INTO monitoring.data_quality_issues (
                        issue_id, batch_id, entity_type, source_row_id, source_row_number,
                        source_file, rule_code, severity, reason, disposition, detected_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    execute_batch(cur, insert_issue_sql, issue_tuples)

                # 7. Bulk insert quarantine records
                if quarantine_rows:
                    insert_quarantine_sql = """
                    INSERT INTO quarantine.quarantined_records (
                        quarantine_id, batch_id, entity_type, source_row_id,
                        source_row_number, source_file, primary_rule_code, issue_count
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                    """
                    execute_batch(cur, insert_quarantine_sql, quarantine_rows)

                # 8. Determine batch final status and update monitoring.etl_batch_runs
                if summary.records_rejected > 0:
                    summary.batch_status = BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS
                else:
                    summary.batch_status = BATCH_STATUS_SUCCEEDED

                cur.execute("""
                    UPDATE monitoring.etl_batch_runs
                    SET status = %s,
                        records_valid = %s,
                        records_rejected = %s
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

            if not outcome.is_rejected and clean_id:
                valid_ids.add(clean_id)

            outcomes.append(outcome)

        # Include previously validated branches from other batches (not quarantined)
        cur.execute("""
            SELECT DISTINCT branch_id FROM staging.stg_branches
            WHERE batch_id != %s AND branch_id IS NOT NULL AND TRIM(branch_id) != ''
              AND source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'BRANCH'
              );
        """, (batch_id,))
        for (prev_id,) in cur.fetchall():
            if prev_id and prev_id.strip():
                valid_ids.add(prev_id.strip())

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

        # Include previously validated customers from other batches (not quarantined)
        cur.execute("""
            SELECT DISTINCT customer_id FROM staging.stg_customers
            WHERE batch_id != %s AND customer_id IS NOT NULL AND TRIM(customer_id) != ''
              AND source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'CUSTOMER'
              );
        """, (batch_id,))
        for (prev_id,) in cur.fetchall():
            if prev_id and prev_id.strip():
                valid_ids.add(prev_id.strip())

        return valid_ids, outcomes

    def _validate_accounts(
        self,
        cur: psycopg2.extensions.cursor,
        batch_id: str,
        valid_customer_ids: Set[str],
        valid_branch_ids: Set[str],
    ) -> Tuple[Set[str], List[RowValidationOutcome]]:
        cur.execute("""
            SELECT source_row_id, source_row_number, source_file,
                   account_id, customer_id, branch_id, account_type, account_status,
                   opened_date_raw, currency
            FROM staging.stg_accounts
            WHERE batch_id = %s
            ORDER BY source_row_number;
        """, (batch_id,))
        rows = cur.fetchall()

        valid_ids: Set[str] = set()
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

            if not outcome.is_rejected and clean_id:
                valid_ids.add(clean_id)

            outcomes.append(outcome)

        # Include previously validated accounts from other batches (not quarantined)
        cur.execute("""
            SELECT DISTINCT account_id FROM staging.stg_accounts
            WHERE batch_id != %s AND account_id IS NOT NULL AND TRIM(account_id) != ''
              AND source_row_id NOT IN (
                  SELECT source_row_id FROM quarantine.quarantined_records WHERE entity_type = 'ACCOUNT'
              );
        """, (batch_id,))
        for (prev_id,) in cur.fetchall():
            if prev_id and prev_id.strip():
                valid_ids.add(prev_id.strip())

        return valid_ids, outcomes

    def _validate_transactions(
        self,
        cur: psycopg2.extensions.cursor,
        batch_id: str,
        valid_account_ids: Set[str],
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

            # 2. Account reference check
            clean_aid = (a_id or "").strip()
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
            elif clean_aid not in valid_account_ids:
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

            # 3. Transaction Type check
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

            # 4. Amount check (Decimal parsing and type-specific rules)
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

            # 5. Currency check
            clean_curr = (curr or "").strip()
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

            # 6. Timestamp check (Timezone-aware parsing; past/late timestamps are valid)
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

            # 7. Status check
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

            # 8. Channel check
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
