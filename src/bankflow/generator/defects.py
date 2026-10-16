"""
Defect configuration and injection policies for BankFlow synthetic data generation.
Allows clean generation or deterministic injection of specific quality defects.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DefectConfig:
    """Controls which defects to inject and how many of each."""
    enabled: bool = False
    missing_txn_id_count: int = 0
    duplicate_txn_id_count: int = 0
    missing_account_id_count: int = 0
    unknown_account_ref_count: int = 0
    unsupported_type_count: int = 0
    missing_currency_count: int = 0
    invalid_timestamp_count: int = 0
    missing_amount_count: int = 0
    non_numeric_amount_count: int = 0
    amount_rule_violation_count: int = 0
    unsupported_status_count: int = 0
    unsupported_channel_count: int = 0
    late_arriving_count: int = 0
    corrupt_header: bool = False
    empty_file: bool = False

    @classmethod
    def clean(cls) -> DefectConfig:
        """Clean dataset with zero injected defects."""
        return cls(enabled=False)

    @classmethod
    def standard_test_defects(cls) -> DefectConfig:
        """Standard fixture configuration injecting 1 occurrence of each defect scenario."""
        return cls(
            enabled=True,
            missing_txn_id_count=1,
            duplicate_txn_id_count=1,
            missing_account_id_count=1,
            unknown_account_ref_count=1,
            unsupported_type_count=1,
            missing_currency_count=1,
            invalid_timestamp_count=1,
            missing_amount_count=1,
            non_numeric_amount_count=1,
            amount_rule_violation_count=1,
            unsupported_status_count=1,
            unsupported_channel_count=1,
            late_arriving_count=1,
            corrupt_header=False,
            empty_file=False,
        )
