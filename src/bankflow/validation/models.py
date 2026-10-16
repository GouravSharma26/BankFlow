"""
Data models and typed structures for the validation and quarantine engine.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bankflow.constants import (
    DISPOSITION_ACCEPTED,
    DISPOSITION_REJECTED,
    DISPOSITION_WARNED,
    SEVERITY_ERROR,
    SEVERITY_WARNING,
)


@dataclass
class ValidationIssue:
    """Represents a discrete data-quality rule violation or warning on a source row."""

    batch_id: str
    entity_type: str
    source_file: str
    source_row_number: int
    rule_code: str
    severity: str
    reason: str
    disposition: str = DISPOSITION_REJECTED
    source_row_id: Optional[int] = None
    issue_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_db_tuple(self) -> tuple:
        """Return tuple matching monitoring.data_quality_issues column insertion."""
        return (
            self.issue_id,
            self.batch_id,
            self.entity_type,
            self.source_row_id,
            self.source_row_number,
            self.source_file,
            self.rule_code,
            self.severity,
            self.reason,
            self.disposition,
            self.detected_at,
        )


@dataclass
class RowValidationOutcome:
    """Validation outcome for a single staged record."""

    source_row_id: int
    source_row_number: int
    entity_type: str
    issues: List[ValidationIssue] = field(default_factory=list)
    cleaned_record: Optional[Dict[str, Any]] = None

    @property
    def is_rejected(self) -> bool:
        """True if any detected issue on this row has severity ERROR."""
        return any(i.severity == SEVERITY_ERROR for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        """True if row has warning issues but no error issues."""
        return not self.is_rejected and any(i.severity == SEVERITY_WARNING for i in self.issues)

    @property
    def disposition(self) -> str:
        """Compute the final row disposition."""
        if self.is_rejected:
            return DISPOSITION_REJECTED
        if self.has_warnings:
            return DISPOSITION_WARNED
        return DISPOSITION_ACCEPTED


@dataclass
class BatchValidationSummary:
    """High-level summary and accounting of a batch validation run."""

    batch_id: str
    records_evaluated: int = 0
    records_valid: int = 0
    records_rejected: int = 0
    records_warned: int = 0
    records_skipped: int = 0
    total_issues_count: int = 0
    issues_by_rule: Dict[str, int] = field(default_factory=dict)
    issues_by_severity: Dict[str, int] = field(default_factory=dict)
    batch_status: str = "SUCCEEDED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "records_evaluated": self.records_evaluated,
            "records_valid": self.records_valid,
            "records_rejected": self.records_rejected,
            "records_warned": self.records_warned,
            "records_skipped": self.records_skipped,
            "total_issues_count": self.total_issues_count,
            "issues_by_rule": self.issues_by_rule,
            "issues_by_severity": self.issues_by_severity,
            "batch_status": self.batch_status,
        }
