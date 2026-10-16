"""
Deterministic synthetic data generator for BankFlow.
Generates branches, customers, accounts, and transactions with reproducible seeds
and controlled defect injection. Uses synthetic identifiers only (no real customer PII).
"""

from __future__ import annotations

import csv
import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from bankflow.constants import (
    ACCOUNT_STATUS_CLOSED,
    ACCOUNT_STATUS_OPEN,
    ACCOUNT_TYPE_CHECKING,
    ACCOUNT_TYPE_SAVINGS,
    ACCOUNTS_COLUMNS,
    BRANCHES_COLUMNS,
    CHANNEL_ATM,
    CHANNEL_BRANCH,
    CHANNEL_MOBILE,
    CHANNEL_ONLINE,
    CURRENCY_USD,
    CUSTOMER_STATUS_ACTIVE,
    CUSTOMERS_COLUMNS,
    SEGMENT_PREMIUM,
    SEGMENT_RETAIL,
    SEGMENT_SMALL_BUSINESS,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_REVERSED,
    TRANSACTIONS_COLUMNS,
    TYPE_DEPOSIT,
    TYPE_FEE,
    TYPE_PAYMENT,
    TYPE_REVERSAL,
    TYPE_TRANSFER,
    TYPE_WITHDRAWAL,
)
from bankflow.generator.defects import DefectConfig


class SyntheticDataGenerator:
    """Generates deterministic synthetic banking datasets."""

    def __init__(self, seed: int = 42, defect_config: Optional[DefectConfig] = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.defect_config = defect_config or DefectConfig.clean()

    def generate_branches(self, count: int = 5) -> List[Dict[str, str]]:
        """Generate synthetic branches."""
        regions = ["NORTH", "SOUTH", "EAST", "WEST", "CENTRAL"]
        name_prefixes = ["Downtown", "Metro", "Harbor", "West End", "Northside", "Uptown", "Valley"]
        name_suffixes = ["Financial Center", "Branch", "Hub", "Plaza", "Commercial Office"]

        branches: List[Dict[str, str]] = []
        for i in range(1, count + 1):
            prefix = self.rng.choice(name_prefixes)
            suffix = self.rng.choice(name_suffixes)
            region = regions[(i - 1) % len(regions)]
            branch_id = f"BR-{i:03d}"
            branch_name = f"{prefix} {suffix} {i}"
            branches.append({
                "branch_id": branch_id,
                "branch_name": branch_name,
                "region": region,
            })
        return branches

    def generate_customers(
        self,
        count: int = 25,
        start_date: str = "2023-01-01",
        end_date: str = "2025-12-31",
    ) -> List[Dict[str, str]]:
        """Generate synthetic customers with opaque identifiers."""
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        if end_dt < start_dt:
            raise ValueError(f"Customer end_date ({end_date}) cannot be before start_date ({start_date})")
        total_days = (end_dt - start_dt).days

        segments = [SEGMENT_RETAIL, SEGMENT_PREMIUM, SEGMENT_SMALL_BUSINESS]
        segment_weights = [0.70, 0.20, 0.10]

        customers: List[Dict[str, str]] = []
        for i in range(1, count + 1):
            cust_id = f"CUST-{i:06d}"
            segment = self.rng.choices(segments, weights=segment_weights, k=1)[0]
            created_offset = self.rng.randint(0, max(0, total_days))
            created_date = start_dt + timedelta(days=created_offset)
            status = CUSTOMER_STATUS_ACTIVE if self.rng.random() > 0.05 else "INACTIVE"

            customers.append({
                "customer_id": cust_id,
                "customer_segment": segment,
                "created_date": created_date.isoformat(),
                "customer_status": status,
            })
        return customers

    def generate_accounts(
        self,
        customers: List[Dict[str, str]],
        branches: List[Dict[str, str]],
        count: int = 40,
    ) -> List[Dict[str, str]]:
        """Generate synthetic accounts linked to customers and branches."""
        if not customers:
            raise ValueError("Cannot generate accounts without customers.")
        if not branches:
            raise ValueError("Cannot generate accounts without branches.")

        account_types = [ACCOUNT_TYPE_CHECKING, ACCOUNT_TYPE_SAVINGS]
        statuses = [ACCOUNT_STATUS_OPEN, ACCOUNT_STATUS_CLOSED]
        status_weights = [0.95, 0.05]

        accounts: List[Dict[str, str]] = []
        for i in range(1, count + 1):
            acc_id = f"ACC-{i:06d}"
            cust = self.rng.choice(customers)
            branch = self.rng.choice(branches)
            acc_type = self.rng.choice(account_types)
            status = self.rng.choices(statuses, weights=status_weights, k=1)[0]

            # Opened date is on or after customer creation date
            cust_created = datetime.strptime(cust["created_date"], "%Y-%m-%d").date()
            days_after = self.rng.randint(0, 180)
            opened_date = cust_created + timedelta(days=days_after)

            accounts.append({
                "account_id": acc_id,
                "customer_id": cust["customer_id"],
                "branch_id": branch["branch_id"],
                "account_type": acc_type,
                "account_status": status,
                "opened_date": opened_date.isoformat(),
                "currency": CURRENCY_USD,
            })
        return accounts

    def generate_transactions(
        self,
        accounts: List[Dict[str, str]],
        count: int = 100,
        start_date: str = "2026-01-01",
        end_date: str = "2026-03-31",
    ) -> List[Dict[str, str]]:
        """Generate synthetic transactions with deterministic defect injection."""
        if not accounts:
            raise ValueError("Cannot generate transactions without accounts.")

        start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if end_dt < start_dt:
            raise ValueError(f"Transaction end_date ({end_date}) cannot be before start_date ({start_date})")
        total_seconds = int((end_dt - start_dt).total_seconds())

        types = [TYPE_DEPOSIT, TYPE_WITHDRAWAL, TYPE_TRANSFER, TYPE_PAYMENT, TYPE_FEE]
        type_weights = [0.35, 0.30, 0.15, 0.15, 0.05]

        channels = [CHANNEL_ONLINE, CHANNEL_MOBILE, CHANNEL_ATM, CHANNEL_BRANCH]
        channel_weights = [0.45, 0.35, 0.12, 0.08]

        statuses = [STATUS_COMPLETED, STATUS_PENDING, STATUS_FAILED]
        status_weights = [0.94, 0.04, 0.02]

        transactions: List[Dict[str, str]] = []
        for i in range(1, count + 1):
            txn_id = f"TXN-{i:08d}"
            acc = self.rng.choice(accounts)
            txn_type = self.rng.choices(types, weights=type_weights, k=1)[0]
            channel = self.rng.choices(channels, weights=channel_weights, k=1)[0]
            status = self.rng.choices(statuses, weights=status_weights, k=1)[0]

            offset_sec = self.rng.randint(0, max(1, total_seconds))
            ts = start_dt + timedelta(seconds=offset_sec)

            # Generate monetary amount using Decimal
            if txn_type == TYPE_FEE:
                cents = self.rng.randint(100, 3500)
            elif txn_type in (TYPE_WITHDRAWAL, TYPE_PAYMENT):
                cents = self.rng.randint(500, 50000)
            elif txn_type == TYPE_DEPOSIT:
                cents = self.rng.randint(2000, 150000)
            else:  # TRANSFER
                cents = self.rng.randint(1000, 80000)

            amount_dec = (Decimal(cents) / Decimal(100)).quantize(Decimal("0.01"))
            amount_str = f"{amount_dec:.2f}"

            counterparty = ""
            if txn_type == TYPE_TRANSFER:
                other_acc = self.rng.choice(accounts)
                if other_acc["account_id"] != acc["account_id"]:
                    counterparty = other_acc["account_id"]

            transactions.append({
                "transaction_id": txn_id,
                "account_id": acc["account_id"],
                "transaction_type": txn_type,
                "amount": amount_str,
                "currency": CURRENCY_USD,
                "transaction_timestamp": ts.isoformat(),
                "status": status,
                "channel": channel,
                "counterparty_account_id": counterparty,
                "source_system": "CORE_BANKING",
            })

        # Inject controlled defect scenarios if enabled
        if self.defect_config.enabled and transactions:
            self._inject_defects(transactions, accounts, start_dt)

        return transactions

    def _inject_defects(
        self,
        txns: List[Dict[str, str]],
        accounts: List[Dict[str, str]],
        start_dt: datetime,
    ) -> None:
        """Inject defects into transaction rows according to DefectConfig."""
        dc = self.defect_config
        idx = 0

        # 1. Missing transaction ID
        for _ in range(dc.missing_txn_id_count):
            if idx < len(txns):
                txns[idx]["transaction_id"] = ""
                idx += 1

        # 2. Duplicate event ID (works even if idx == 0)
        for _ in range(dc.duplicate_txn_id_count):
            if idx < len(txns) and len(txns) > 1:
                source_idx = 0 if idx > 0 else 1
                txns[idx]["transaction_id"] = txns[source_idx]["transaction_id"]
                idx += 1

        # 3. Missing account ID
        for _ in range(dc.missing_account_id_count):
            if idx < len(txns):
                txns[idx]["account_id"] = ""
                idx += 1

        # 4. Unknown account reference
        for _ in range(dc.unknown_account_ref_count):
            if idx < len(txns):
                txns[idx]["account_id"] = "ACC-999999"
                idx += 1

        # 5. Unsupported transaction type
        for _ in range(dc.unsupported_type_count):
            if idx < len(txns):
                txns[idx]["transaction_type"] = "CRYPTO_TRADE"
                idx += 1

        # 6. Missing currency
        for _ in range(dc.missing_currency_count):
            if idx < len(txns):
                txns[idx]["currency"] = ""
                idx += 1

        # 7. Invalid timestamp
        for _ in range(dc.invalid_timestamp_count):
            if idx < len(txns):
                txns[idx]["transaction_timestamp"] = "INVALID_TIMESTAMP_2026"
                idx += 1

        # 8. Missing amount
        for _ in range(dc.missing_amount_count):
            if idx < len(txns):
                txns[idx]["amount"] = ""
                idx += 1

        # 9. Non-numeric amount
        for _ in range(dc.non_numeric_amount_count):
            if idx < len(txns):
                txns[idx]["amount"] = "TEN_DOLLARS"
                idx += 1

        # 10. Amount rule violation (e.g. negative amount)
        for _ in range(dc.amount_rule_violation_count):
            if idx < len(txns):
                txns[idx]["transaction_type"] = TYPE_DEPOSIT
                txns[idx]["amount"] = "-150.00"
                idx += 1

        # 11. Unsupported status
        for _ in range(dc.unsupported_status_count):
            if idx < len(txns):
                txns[idx]["status"] = "IN_DISPUTE_UNKNOWN"
                idx += 1

        # 12. Unsupported channel
        for _ in range(dc.unsupported_channel_count):
            if idx < len(txns):
                txns[idx]["channel"] = "TELEPATHY"
                idx += 1

        # 13. Late-arriving transaction from a prior event date
        for _ in range(dc.late_arriving_count):
            if idx < len(txns):
                prior_ts = start_dt - timedelta(days=60)
                txns[idx]["transaction_timestamp"] = prior_ts.isoformat()
                idx += 1

    def export_all(
        self,
        output_dir: Path,
        num_branches: int = 5,
        num_customers: int = 25,
        num_accounts: int = 40,
        num_transactions: int = 100,
        start_date: str = "2026-01-01",
        end_date: str = "2026-03-31",
    ) -> Dict[str, Path]:
        """Generate full synthetic dataset and save to CSV files."""
        output_dir.mkdir(parents=True, exist_ok=True)

        branches = self.generate_branches(num_branches)
        customers = self.generate_customers(num_customers)
        accounts = self.generate_accounts(customers, branches, num_accounts)
        transactions = self.generate_transactions(
            accounts,
            num_transactions,
            start_date=start_date,
            end_date=end_date,
        )

        files = {
            "branches": output_dir / "branches.csv",
            "customers": output_dir / "customers.csv",
            "accounts": output_dir / "accounts.csv",
            "transactions": output_dir / "transactions.csv",
        }

        self._write_csv(files["branches"], BRANCHES_COLUMNS, branches)
        self._write_csv(files["customers"], CUSTOMERS_COLUMNS, customers)
        self._write_csv(files["accounts"], ACCOUNTS_COLUMNS, accounts)

        # Handle corrupt header or empty file defect cases if specified
        if self.defect_config.corrupt_header:
            corrupt_cols = ["wrong_col_1", "wrong_col_2", "wrong_col_3"]
            self._write_csv(files["transactions"], corrupt_cols, transactions)
        elif self.defect_config.empty_file:
            self._write_csv(files["transactions"], TRANSACTIONS_COLUMNS, [])
        else:
            self._write_csv(files["transactions"], TRANSACTIONS_COLUMNS, transactions)

        return files

    @staticmethod
    def _write_csv(path: Path, fieldnames: List[str], rows: List[Dict[str, Any]]) -> None:
        """Write a list of dicts to CSV with exact header names."""
        with open(path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
