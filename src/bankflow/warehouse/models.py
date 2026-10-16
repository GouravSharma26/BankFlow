"""
Data models for the Warehouse Loading and Reconciliation layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional, Tuple


@dataclass
class WarehouseLoadingSummary:
    """Summary of warehouse dimension and fact loading for an ETL batch."""

    batch_id: str
    branches_loaded: int = 0
    customers_loaded: int = 0
    accounts_loaded: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    status: str = "SUCCEEDED"
    reconciliation_status: Optional[str] = None
    error_summary: Optional[str] = None

    @property
    def total_facts_processed(self) -> int:
        return self.records_inserted + self.records_skipped


@dataclass
class ReconciliationReport:
    """Detailed audit report comparing staging, validation, and warehouse layers."""

    batch_id: str
    is_reconciled: bool = False
    extracted_count: int = 0
    staged_count: int = 0
    valid_count: int = 0
    rejected_count: int = 0
    inserted_count: int = 0
    skipped_count: int = 0
    quarantined_count: int = 0
    staging_value_by_currency_status: Dict[Tuple[str, str], Decimal] = field(default_factory=dict)
    warehouse_value_by_currency_status: Dict[Tuple[str, str], Decimal] = field(default_factory=dict)
    discrepancies: List[str] = field(default_factory=list)

    def to_summary_dict(self) -> Dict[str, object]:
        return {
            "batch_id": self.batch_id,
            "is_reconciled": self.is_reconciled,
            "counts": {
                "extracted": self.extracted_count,
                "staged": self.staged_count,
                "valid": self.valid_count,
                "rejected": self.rejected_count,
                "inserted": self.inserted_count,
                "skipped": self.skipped_count,
                "quarantined": self.quarantined_count,
            },
            "discrepancies": self.discrepancies,
        }
