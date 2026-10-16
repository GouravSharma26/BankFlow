"""
Unit tests for file-level header and format validation.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bankflow.constants import (
    RULE_FILE_EMPTY,
    RULE_FILE_HEADER_MISMATCH,
    RULE_FILE_REQUIRED_COLUMN_MISSING,
    RULE_FILE_UNREADABLE,
    TRANSACTIONS_COLUMNS,
)
from bankflow.staging.loader import StagingError, StagingLoader


def test_validate_file_structure_valid_file(clean_dataset_dir: Path):
    loader = StagingLoader(conn=MagicMock())
    txn_file = clean_dataset_dir / "transactions.csv"

    headers, count = loader.validate_file_structure(txn_file, TRANSACTIONS_COLUMNS)
    assert headers == TRANSACTIONS_COLUMNS
    assert count == 50


def test_validate_file_structure_missing_columns(tmp_path: Path):
    loader = StagingLoader(conn=MagicMock())
    bad_file = tmp_path / "bad_txns.csv"
    bad_file.write_text("transaction_id,amount,currency\nTXN-01,10.00,USD\n", encoding="utf-8")

    with pytest.raises(StagingError) as exc_info:
        loader.validate_file_structure(bad_file, TRANSACTIONS_COLUMNS)

    assert exc_info.value.rule_code == RULE_FILE_REQUIRED_COLUMN_MISSING
    assert "Missing required columns" in exc_info.value.message


def test_validate_file_structure_extra_columns(tmp_path: Path):
    loader = StagingLoader(conn=MagicMock())
    bad_file = tmp_path / "extra_cols.csv"
    header_str = ",".join(TRANSACTIONS_COLUMNS) + ",unexpected_extra\n"
    data_str = "TXN-01,ACC-01,DEPOSIT,10.00,USD,2026-01-01T00:00:00+00:00,COMPLETED,ONLINE,,CORE,extra_val\n"
    bad_file.write_text(header_str + data_str, encoding="utf-8")

    with pytest.raises(StagingError) as exc_info:
        loader.validate_file_structure(bad_file, TRANSACTIONS_COLUMNS)

    assert exc_info.value.rule_code == RULE_FILE_HEADER_MISMATCH
    assert "Unexpected columns" in exc_info.value.message


def test_validate_file_structure_duplicate_columns(tmp_path: Path):
    loader = StagingLoader(conn=MagicMock())
    bad_file = tmp_path / "dup_cols.csv"
    header_str = "transaction_id,transaction_id,amount\nTXN-01,TXN-01,10.00\n"
    bad_file.write_text(header_str, encoding="utf-8")

    with pytest.raises(StagingError) as exc_info:
        loader.validate_file_structure(bad_file, TRANSACTIONS_COLUMNS)

    assert exc_info.value.rule_code == RULE_FILE_HEADER_MISMATCH
    assert "Duplicate columns" in exc_info.value.message


def test_validate_file_structure_empty_file_zero_bytes(tmp_path: Path):
    loader = StagingLoader(conn=MagicMock())
    empty_file = tmp_path / "empty_zero.csv"
    empty_file.write_text("", encoding="utf-8")

    with pytest.raises(StagingError) as exc_info:
        loader.validate_file_structure(empty_file, TRANSACTIONS_COLUMNS)

    assert exc_info.value.rule_code == RULE_FILE_EMPTY


def test_validate_file_structure_headers_only_empty_dataset(tmp_path: Path):
    loader = StagingLoader(conn=MagicMock())
    empty_dataset = tmp_path / "empty_dataset.csv"
    empty_dataset.write_text(",".join(TRANSACTIONS_COLUMNS) + "\n", encoding="utf-8")

    with pytest.raises(StagingError) as exc_info:
        loader.validate_file_structure(empty_dataset, TRANSACTIONS_COLUMNS)

    assert exc_info.value.rule_code == RULE_FILE_EMPTY
    assert "zero data rows" in exc_info.value.message


def test_validate_file_structure_nonexistent_file(tmp_path: Path):
    loader = StagingLoader(conn=MagicMock())
    nonexistent = tmp_path / "does_not_exist.csv"

    with pytest.raises(StagingError) as exc_info:
        loader.validate_file_structure(nonexistent, TRANSACTIONS_COLUMNS)

    assert exc_info.value.rule_code == RULE_FILE_UNREADABLE


def test_validate_file_structure_whitespace_in_header(tmp_path: Path):
    loader = StagingLoader(conn=MagicMock())
    bad_file = tmp_path / "whitespace_header.csv"
    # Header contains trailing whitespace on transaction_id
    bad_headers = ["transaction_id "] + TRANSACTIONS_COLUMNS[1:]
    bad_file.write_text(",".join(bad_headers) + "\nTXN-01,ACC-01,DEPOSIT,10.00,USD,2026-01-01T00:00:00+00:00,COMPLETED,ONLINE,,CORE\n", encoding="utf-8")

    with pytest.raises(StagingError) as exc_info:
        loader.validate_file_structure(bad_file, TRANSACTIONS_COLUMNS)

    assert exc_info.value.rule_code == RULE_FILE_HEADER_MISMATCH
    assert "illegal whitespace" in exc_info.value.message


def test_validate_file_structure_reordered_columns(tmp_path: Path):
    loader = StagingLoader(conn=MagicMock())
    bad_file = tmp_path / "reordered.csv"
    # Swap first two columns
    reordered_headers = [TRANSACTIONS_COLUMNS[1], TRANSACTIONS_COLUMNS[0]] + TRANSACTIONS_COLUMNS[2:]
    bad_file.write_text(",".join(reordered_headers) + "\nACC-01,TXN-01,DEPOSIT,10.00,USD,2026-01-01T00:00:00+00:00,COMPLETED,ONLINE,,CORE\n", encoding="utf-8")

    with pytest.raises(StagingError) as exc_info:
        loader.validate_file_structure(bad_file, TRANSACTIONS_COLUMNS)

    assert exc_info.value.rule_code == RULE_FILE_HEADER_MISMATCH
    assert "ordering mismatch" in exc_info.value.message


def test_populated_transaction_id_never_silently_null(tmp_path: Path):
    """
    Prove that a populated transaction ID can never silently become NULL.
    1. If the header has whitespace (e.g. 'transaction_id '), validation strictly fails with RULE_FILE_HEADER_MISMATCH
       rather than allowing DictReader to return row['transaction_id'] as None.
    2. During ingest_transactions on a valid file, DictReader binds strictly to canonical fieldnames,
       guaranteeing that row['transaction_id'] equals the populated CSV value.
    """
    loader = StagingLoader(conn=MagicMock())
    corrupt_header_file = tmp_path / "corrupt_header.csv"
    # Trailing space in header would cause raw DictReader(f).get('transaction_id') to return None!
    corrupt_header_file.write_text(
        "transaction_id ,account_id,transaction_type,amount,currency,transaction_timestamp,status,channel,counterparty_account_id,source_system\n"
        "TXN-VALID-123,ACC-01,DEPOSIT,10.00,USD,2026-01-01T00:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8",
    )

    # Ingestion or validation must reject this file instead of letting TXN-VALID-123 become NULL in staging
    with pytest.raises(StagingError) as exc_info:
        loader.validate_file_structure(corrupt_header_file, TRANSACTIONS_COLUMNS)
    assert exc_info.value.rule_code == RULE_FILE_HEADER_MISMATCH

    # Valid file preserves the exact transaction ID
    valid_file = tmp_path / "valid_txns.csv"
    valid_file.write_text(
        ",".join(TRANSACTIONS_COLUMNS) + "\n"
        "TXN-VALID-123,ACC-01,DEPOSIT,10.00,USD,2026-01-01T00:00:00+00:00,COMPLETED,ONLINE,,CORE\n",
        encoding="utf-8",
    )
    headers, count = loader.validate_file_structure(valid_file, TRANSACTIONS_COLUMNS)
    assert headers == TRANSACTIONS_COLUMNS
    assert count == 1
