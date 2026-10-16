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
