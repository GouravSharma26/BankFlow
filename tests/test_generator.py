"""
Unit tests for the deterministic synthetic data generator.
"""

from decimal import Decimal
from pathlib import Path

from bankflow.constants import (
    ACCOUNTS_COLUMNS,
    BRANCHES_COLUMNS,
    CUSTOMERS_COLUMNS,
    TRANSACTIONS_COLUMNS,
)
from bankflow.generator.defects import DefectConfig
from bankflow.generator.generator import SyntheticDataGenerator


def test_generator_determinism():
    gen1 = SyntheticDataGenerator(seed=12345)
    gen2 = SyntheticDataGenerator(seed=12345)

    branches1 = gen1.generate_branches(count=5)
    branches2 = gen2.generate_branches(count=5)
    assert branches1 == branches2

    cust1 = gen1.generate_customers(count=10)
    cust2 = gen2.generate_customers(count=10)
    assert cust1 == cust2

    acc1 = gen1.generate_accounts(cust1, branches1, count=15)
    acc2 = gen2.generate_accounts(cust2, branches2, count=15)
    assert acc1 == acc2

    txns1 = gen1.generate_transactions(acc1, count=30)
    txns2 = gen2.generate_transactions(acc2, count=30)
    assert txns1 == txns2


def test_generator_different_seeds():
    gen1 = SyntheticDataGenerator(seed=100)
    gen2 = SyntheticDataGenerator(seed=200)

    branches1 = gen1.generate_branches(5)
    branches2 = gen2.generate_branches(5)
    assert branches1 != branches2


def test_clean_generator_column_contracts():
    gen = SyntheticDataGenerator(seed=42)
    branches = gen.generate_branches(3)
    customers = gen.generate_customers(5)
    accounts = gen.generate_accounts(customers, branches, 8)
    transactions = gen.generate_transactions(accounts, 20)

    for b in branches:
        assert set(b.keys()) == set(BRANCHES_COLUMNS)
    for c in customers:
        assert set(c.keys()) == set(CUSTOMERS_COLUMNS)
    for a in accounts:
        assert set(a.keys()) == set(ACCOUNTS_COLUMNS)
    for t in transactions:
        assert set(t.keys()) == set(TRANSACTIONS_COLUMNS)
        # Amounts should parse to valid Decimal
        amt = Decimal(t["amount"])
        assert amt > Decimal("0.00")


def test_defect_injection_scenarios():
    dc = DefectConfig.standard_test_defects()
    gen = SyntheticDataGenerator(seed=42, defect_config=dc)

    branches = gen.generate_branches(3)
    customers = gen.generate_customers(5)
    accounts = gen.generate_accounts(customers, branches, 8)
    txns = gen.generate_transactions(accounts, 50)

    txn_ids = [t["transaction_id"] for t in txns]
    account_ids = [t["account_id"] for t in txns]
    types = [t["transaction_type"] for t in txns]
    amounts = [t["amount"] for t in txns]
    timestamps = [t["transaction_timestamp"] for t in txns]
    currencies = [t["currency"] for t in txns]
    channels = [t["channel"] for t in txns]
    statuses = [t["status"] for t in txns]

    # Verify injected defect conditions exist in the output
    assert "" in txn_ids, "Missing transaction ID defect not found"
    assert len(txn_ids) != len(set(txn_ids)), "Duplicate transaction ID defect not found"
    # Ensure standard defect configuration produces a duplicate of a valid, non-empty ID
    non_empty_ids = [tid for tid in txn_ids if tid]
    assert len(non_empty_ids) != len(set(non_empty_ids)), "Duplicate of non-empty transaction ID defect not found"
    dup_non_empty = [tid for tid in set(non_empty_ids) if non_empty_ids.count(tid) > 1]
    assert len(dup_non_empty) >= 1, "Duplicate of valid non-empty transaction ID not found"

    assert "" in account_ids, "Missing account ID defect not found"
    assert "ACC-999999" in account_ids, "Unknown account reference defect not found"
    assert "CRYPTO_TRADE" in types, "Unsupported transaction type defect not found"
    assert "" in currencies, "Missing currency defect not found"
    assert "INVALID_TIMESTAMP_2026" in timestamps, "Invalid timestamp defect not found"
    assert "" in amounts, "Missing amount defect not found"
    assert "TEN_DOLLARS" in amounts, "Non-numeric amount defect not found"
    assert "-150.00" in amounts, "Amount rule violation defect not found"
    assert "IN_DISPUTE_UNKNOWN" in statuses, "Unsupported status defect not found"
    assert "TELEPATHY" in channels, "Unsupported channel defect not found"
    # Verify late-arriving event defect (timestamp from 2025 prior to 2026-01-01 start_date)
    has_prior_timestamp = any("2025-" in ts for ts in timestamps)
    assert has_prior_timestamp, "Late-arriving transaction defect not found"


def test_duplicate_defect_without_missing_txn_id():
    """Verify duplicate defect is injected even when missing_txn_id_count is 0."""
    dc = DefectConfig(enabled=True, missing_txn_id_count=0, duplicate_txn_id_count=2)
    gen = SyntheticDataGenerator(seed=42, defect_config=dc)
    customers = gen.generate_customers(2)
    branches = gen.generate_branches(2)
    accounts = gen.generate_accounts(customers, branches, 2)
    txns = gen.generate_transactions(accounts, 10)
    txn_ids = [t["transaction_id"] for t in txns]

    assert "" not in txn_ids
    assert len(txn_ids) != len(set(txn_ids))


def test_date_range_validation():
    """Verify ValueError is raised when end_date is before start_date."""
    gen = SyntheticDataGenerator(seed=42)
    import pytest

    with pytest.raises(ValueError, match="cannot be before start_date"):
        gen.generate_customers(count=5, start_date="2026-01-01", end_date="2025-01-01")

    customers = gen.generate_customers(2)
    branches = gen.generate_branches(2)
    accounts = gen.generate_accounts(customers, branches, 2)

    with pytest.raises(ValueError, match="cannot be before start_date"):
        gen.generate_transactions(accounts, 10, start_date="2026-05-01", end_date="2026-01-01")


def test_date_range_inclusive_boundaries():
    """Verify that end_date includes transactions up to 23:59:59 UTC."""
    gen = SyntheticDataGenerator(seed=42)
    customers = gen.generate_customers(2)
    branches = gen.generate_branches(2)
    accounts = gen.generate_accounts(customers, branches, 2)

    # Single day boundary check
    txns_single = gen.generate_transactions(
        accounts,
        count=50,
        start_date="2026-06-15",
        end_date="2026-06-15",
    )
    for t in txns_single:
        assert t["transaction_timestamp"].startswith("2026-06-15")
        assert "2026-06-15T00:00:00+00:00" <= t["transaction_timestamp"] <= "2026-06-15T23:59:59+00:00"

    # Multi-day boundary check
    txns_multi = gen.generate_transactions(
        accounts,
        count=100,
        start_date="2026-01-01",
        end_date="2026-01-03",
    )
    for t in txns_multi:
        assert "2026-01-01T00:00:00+00:00" <= t["transaction_timestamp"] <= "2026-01-03T23:59:59+00:00"


def test_cli_generate_date_options(tmp_path: Path):
    """Test CLI argument parsing, custom date ranges, invalid/reversed dates."""
    from click.testing import CliRunner
    from bankflow.__main__ import cli

    runner = CliRunner()

    # 1. Successful custom date range
    out_dir = tmp_path / "cli_dates"
    res = runner.invoke(
        cli,
        [
            "generate",
            "--output-dir", str(out_dir),
            "--start-date", "2026-03-01",
            "--end-date", "2026-03-05",
            "--branches", "2",
            "--customers", "2",
            "--accounts", "2",
            "--transactions", "10",
        ],
    )
    assert res.exit_code == 0
    assert "[OK] Generated 4 CSV files" in res.output
    assert (out_dir / "transactions.csv").exists()

    # 2. Reversed dates (end before start)
    res_reversed = runner.invoke(
        cli,
        [
            "generate",
            "--output-dir", str(tmp_path / "cli_rev"),
            "--start-date", "2026-03-10",
            "--end-date", "2026-03-01",
        ],
    )
    assert res_reversed.exit_code != 0
    assert "cannot be before start date" in res_reversed.output

    # 3. Invalid date format
    res_invalid = runner.invoke(
        cli,
        [
            "generate",
            "--output-dir", str(tmp_path / "cli_inv"),
            "--start-date", "invalid-date",
        ],
    )
    assert res_invalid.exit_code != 0
    assert "Invalid date format" in res_invalid.output


def test_export_all_creates_valid_csvs(tmp_path: Path):
    gen = SyntheticDataGenerator(seed=42)
    files = gen.export_all(
        output_dir=tmp_path,
        num_branches=2,
        num_customers=5,
        num_accounts=5,
        num_transactions=10,
    )

    for entity, path in files.items():
        assert path.exists(), f"File for {entity} was not created"
        assert path.stat().st_size > 0, f"File {path} is empty"
