"""
Strict ISO-8601 Calendar Date Parsing (YYYY-MM-DD).
Enforces exact syntax, calendar validation, and rejects defaults/fallbacks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Optional

STRICT_DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class StrictDateResult:
    """Result of strict date validation and parsing."""

    is_valid: bool
    parsed_date: Optional[date] = None
    error_message: Optional[str] = None

    def __bool__(self) -> bool:
        return self.is_valid

    def __iter__(self):
        """Allows unpacking as (parsed_date, error_message)."""
        return iter((self.parsed_date, self.error_message))


def parse_strict_date(value: Any) -> StrictDateResult:
    """
    Parse and validate a date strictly requiring YYYY-MM-DD syntax and valid calendar date.

    Rules:
    - Must be a string.
    - Exactly YYYY-MM-DD syntax (4 digits, hyphen, 2 digits, hyphen, 2 digits).
    - No leading or trailing whitespace.
    - True calendar date validation (leap year, days per month, month in 1..12).
    - Rejects week dates (e.g. 2026-W03-4), compact dates (e.g. 20260115), or timestamps.
    - Never supplies a default/fallback date.
    - Returns StrictDateResult(is_valid, parsed_date, error_message).
    """
    if value is None:
        return StrictDateResult(
            is_valid=False,
            parsed_date=None,
            error_message="Date value is missing or null.",
        )

    if not isinstance(value, str):
        return StrictDateResult(
            is_valid=False,
            parsed_date=None,
            error_message=f"Date value must be a string, got {type(value).__name__}.",
        )

    if value == "":
        return StrictDateResult(
            is_valid=False,
            parsed_date=None,
            error_message="Date value is empty.",
        )

    if value.strip() == "":
        return StrictDateResult(
            is_valid=False,
            parsed_date=None,
            error_message="Date value contains only whitespace.",
        )

    # Enforce exact syntax YYYY-MM-DD without leading/trailing whitespace
    if not STRICT_DATE_REGEX.match(value):
        return StrictDateResult(
            is_valid=False,
            parsed_date=None,
            error_message=f"Date '{value}' does not match exact YYYY-MM-DD format.",
        )

    # Validate calendar date (days in month, leap year, etc.)
    try:
        dt = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as e:
        return StrictDateResult(
            is_valid=False,
            parsed_date=None,
            error_message=f"Date '{value}' is not a valid calendar date: {e}.",
        )

    return StrictDateResult(
        is_valid=True,
        parsed_date=dt,
        error_message=None,
    )
