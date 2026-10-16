"""
Unit tests for file-level header and format validation.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from bankflow.constants import (
    RULE_FILE_EMPTY,
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


def test_validate_file_structure_empty_file(tmp_path: Path):
    loader = StagingLoader(conn=MagicMock())
    empty_file = tmp_path / "empty.csv"
    empty_file.write_text("", encoding="utf-8")

    with pytest.raises(StagingError) as exc_info:
        loader.validate_file_structure(empty_file, TRANSACTIONS_COLUMNS)

    assert exc_info.value.rule_code == RULE_FILE_EMPTY


def test_validate_file_structure_nonexistent_file(tmp_path: Path):
    loader = StagingLoader(conn=MagicMock())
    nonexistent = tmp_path / "does_not_exist.csv"

    with pytest.raises(StagingError) as exc_info:
        loader.validate_file_structure(nonexistent, TRANSACTIONS_COLUMNS)

    assert exc_info.value.rule_code == RULE_FILE_UNREADABLE
