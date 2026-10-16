"""
Staging loader for BankFlow batch ETL.
Validates file-level headers and ingests raw CSV rows into PostgreSQL staging tables
while capturing full source lineage and batch run metadata.
"""

from __future__ import annotations

import csv
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import execute_batch
from psycopg2.extensions import connection as PgConnection

from bankflow.constants import (
    ACCOUNTS_COLUMNS,
    BATCH_STATUS_FAILED,
    BATCH_STATUS_RUNNING,
    BATCH_STATUS_SUCCEEDED,
    BRANCHES_COLUMNS,
    CUSTOMERS_COLUMNS,
    ENTITY_SCHEMAS,
    RULE_FILE_EMPTY,
    RULE_FILE_REQUIRED_COLUMN_MISSING,
    RULE_FILE_UNREADABLE,
    TRANSACTIONS_COLUMNS,
)
from bankflow.db import transaction


class StagingError(Exception):
    """File-level or staging ingestion failure."""
    def __init__(self, rule_code: str, message: str):
        super().__init__(f"[{rule_code}] {message}")
        self.rule_code = rule_code
        self.message = message


class StagingLoader:
    """Manages file verification, batch registration, and staging ingestion."""

    def __init__(self, conn: PgConnection):
        self.conn = conn

    def register_batch(self, source_name: str, batch_id: Optional[str] = None) -> str:
        """Create a new batch record in monitoring.etl_batch_runs."""
        if not batch_id:
            batch_id = f"batch_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

        now = datetime.now(timezone.utc)
        query = """
        INSERT INTO monitoring.etl_batch_runs (
            batch_id, source_name, started_at, status, records_extracted, records_staged
        ) VALUES (%s, %s, %s, %s, 0, 0);
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (batch_id, source_name, now, BATCH_STATUS_RUNNING))
        self.conn.commit()
        return batch_id

    def update_batch_failure(self, batch_id: str, error_code: str, error_message: str) -> None:
        """Mark a batch as failed with error summary."""
        now = datetime.now(timezone.utc)
        error_summary = f"{error_code}: {error_message}"
        query = """
        UPDATE monitoring.etl_batch_runs
        SET status = %s,
            completed_at = %s,
            error_summary = %s
        WHERE batch_id = %s;
        """
        with self.conn.cursor() as cur:
            cur.execute(query, (BATCH_STATUS_FAILED, now, error_summary, batch_id))
        self.conn.commit()

    def update_batch_success(
        self,
        batch_id: str,
        records_extracted: int,
        records_staged: int,
    ) -> None:
        """Mark a batch as succeeded with final row counts."""
        now = datetime.now(timezone.utc)
        query = """
        UPDATE monitoring.etl_batch_runs
        SET status = %s,
            completed_at = %s,
            records_extracted = %s,
            records_staged = %s
        WHERE batch_id = %s;
        """
        with self.conn.cursor() as cur:
            cur.execute(
                query,
                (BATCH_STATUS_SUCCEEDED, now, records_extracted, records_staged, batch_id),
            )
        self.conn.commit()

    def validate_file_structure(self, file_path: Path, expected_columns: List[str]) -> Tuple[List[str], int]:
        """
        Verify that file exists, is valid UTF-8, and headers strictly match expected columns.
        Returns (headers, data_row_count).
        Raises StagingError on violation.
        """
        if not file_path.exists():
            raise StagingError(RULE_FILE_UNREADABLE, f"File does not exist: {file_path}")

        try:
            with open(file_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                try:
                    header_row = next(reader)
                except StopIteration:
                    raise StagingError(RULE_FILE_EMPTY, f"File is empty (no headers): {file_path}")

                cleaned_headers = [col.strip() for col in header_row]

                # Verify all expected columns are present
                missing_cols = [col for col in expected_columns if col not in cleaned_headers]
                if missing_cols:
                    raise StagingError(
                        RULE_FILE_REQUIRED_COLUMN_MISSING,
                        f"Missing required columns in {file_path.name}: {missing_cols}. Found: {cleaned_headers}",
                    )

                # Count rows
                data_rows = sum(1 for _ in reader)
                return cleaned_headers, data_rows

        except UnicodeDecodeError as ex:
            raise StagingError(RULE_FILE_UNREADABLE, f"Encoding error reading {file_path.name}: {ex}")

    def ingest_branches(self, file_path: Path, batch_id: str) -> int:
        """Ingest branches CSV into staging.stg_branches."""
        _, total_rows = self.validate_file_structure(file_path, BRANCHES_COLUMNS)
        source_file = file_path.name
        rows_to_insert = []

        with open(file_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=1):
                payload_json = json.dumps(row)
                rows_to_insert.append((
                    row.get("branch_id"),
                    row.get("branch_name"),
                    row.get("region"),
                    source_file,
                    batch_id,
                    row_num,
                    payload_json,
                ))

        insert_sql = """
        INSERT INTO staging.stg_branches (
            branch_id, branch_name, region, source_file, batch_id, source_row_number, raw_payload
        ) VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        with transaction(self.conn):
            with self.conn.cursor() as cur:
                execute_batch(cur, insert_sql, rows_to_insert)

        return len(rows_to_insert)

    def ingest_customers(self, file_path: Path, batch_id: str) -> int:
        """Ingest customers CSV into staging.stg_customers."""
        _, total_rows = self.validate_file_structure(file_path, CUSTOMERS_COLUMNS)
        source_file = file_path.name
        rows_to_insert = []

        with open(file_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=1):
                payload_json = json.dumps(row)
                rows_to_insert.append((
                    row.get("customer_id"),
                    row.get("customer_segment"),
                    row.get("created_date"),
                    row.get("customer_status"),
                    source_file,
                    batch_id,
                    row_num,
                    payload_json,
                ))

        insert_sql = """
        INSERT INTO staging.stg_customers (
            customer_id, customer_segment, created_date_raw, customer_status,
            source_file, batch_id, source_row_number, raw_payload
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """
        with transaction(self.conn):
            with self.conn.cursor() as cur:
                execute_batch(cur, insert_sql, rows_to_insert)

        return len(rows_to_insert)

    def ingest_accounts(self, file_path: Path, batch_id: str) -> int:
        """Ingest accounts CSV into staging.stg_accounts."""
        _, total_rows = self.validate_file_structure(file_path, ACCOUNTS_COLUMNS)
        source_file = file_path.name
        rows_to_insert = []

        with open(file_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=1):
                payload_json = json.dumps(row)
                rows_to_insert.append((
                    row.get("account_id"),
                    row.get("customer_id"),
                    row.get("branch_id"),
                    row.get("account_type"),
                    row.get("account_status"),
                    row.get("opened_date"),
                    row.get("currency"),
                    source_file,
                    batch_id,
                    row_num,
                    payload_json,
                ))

        insert_sql = """
        INSERT INTO staging.stg_accounts (
            account_id, customer_id, branch_id, account_type, account_status,
            opened_date_raw, currency, source_file, batch_id, source_row_number, raw_payload
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        with transaction(self.conn):
            with self.conn.cursor() as cur:
                execute_batch(cur, insert_sql, rows_to_insert)

        return len(rows_to_insert)

    def ingest_transactions(self, file_path: Path, batch_id: str) -> int:
        """Ingest transactions CSV into staging.stg_transactions."""
        _, total_rows = self.validate_file_structure(file_path, TRANSACTIONS_COLUMNS)
        source_file = file_path.name
        rows_to_insert = []

        with open(file_path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=1):
                payload_json = json.dumps(row)
                rows_to_insert.append((
                    row.get("transaction_id"),
                    row.get("account_id"),
                    row.get("transaction_type"),
                    row.get("amount"),
                    row.get("currency"),
                    row.get("transaction_timestamp"),
                    row.get("status"),
                    row.get("channel"),
                    row.get("counterparty_account_id"),
                    row.get("source_system"),
                    source_file,
                    batch_id,
                    row_num,
                    payload_json,
                ))

        insert_sql = """
        INSERT INTO staging.stg_transactions (
            transaction_id, account_id, transaction_type, amount_raw, currency,
            transaction_timestamp_raw, status, channel, counterparty_account_id,
            source_system, source_file, batch_id, source_row_number, raw_payload
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        with transaction(self.conn):
            with self.conn.cursor() as cur:
                execute_batch(cur, insert_sql, rows_to_insert)

        return len(rows_to_insert)

    def ingest_dataset_directory(self, data_dir: Path, batch_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Ingest all 4 entities from a dataset directory in reference order:
        branches -> customers -> accounts -> transactions.
        Registers the batch, validates each file, ingests into staging, and records outcome.
        """
        if not batch_id:
            batch_id = self.register_batch(source_name=str(data_dir))

        total_extracted = 0
        total_staged = 0

        entity_files = [
            ("branches", data_dir / "branches.csv", self.ingest_branches, BRANCHES_COLUMNS),
            ("customers", data_dir / "customers.csv", self.ingest_customers, CUSTOMERS_COLUMNS),
            ("accounts", data_dir / "accounts.csv", self.ingest_accounts, ACCOUNTS_COLUMNS),
            ("transactions", data_dir / "transactions.csv", self.ingest_transactions, TRANSACTIONS_COLUMNS),
        ]

        entity_counts: Dict[str, int] = {}
        try:
            for entity_name, path, ingest_func, expected_cols in entity_files:
                if not path.exists():
                    raise StagingError(RULE_FILE_UNREADABLE, f"Missing required entity file: {path.name}")

                _, extracted_count = self.validate_file_structure(path, expected_cols)
                total_extracted += extracted_count

                staged_count = ingest_func(path, batch_id)
                total_staged += staged_count
                entity_counts[entity_name] = staged_count

            self.update_batch_success(batch_id, total_extracted, total_staged)
            return {
                "batch_id": batch_id,
                "status": BATCH_STATUS_SUCCEEDED,
                "records_extracted": total_extracted,
                "records_staged": total_staged,
                "entity_counts": entity_counts,
            }

        except StagingError as err:
            self.update_batch_failure(batch_id, err.rule_code, err.message)
            return {
                "batch_id": batch_id,
                "status": BATCH_STATUS_FAILED,
                "error_code": err.rule_code,
                "error_message": err.message,
                "records_extracted": total_extracted,
                "records_staged": total_staged,
                "entity_counts": entity_counts,
            }
        except Exception as ex:
            self.update_batch_failure(batch_id, "UNEXPECTED_ERROR", str(ex))
            raise
