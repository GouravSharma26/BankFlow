"""
Unit tests for BankFlow Reporting API input validators:
- Strict YYYY-MM-DD parsing (rejection of compact dates, ISO week dates, invalid calendars, malformed inputs)
- Canonical quality disposition validation (ACCEPTED, REJECTED, WARNED, SKIPPED)
- Supported currency validation (USD, EUR, GBP)
"""

from __future__ import annotations

from datetime import date
import pytest
from fastapi import HTTPException

from bankflow.api.validators import (
    validate_currency,
    validate_date_range,
    validate_disposition,
    ALLOWED_DISPOSITIONS,
)


class TestStrictDateValidation:
    """Test strict YYYY-MM-DD parsing in validate_date_range."""

    def test_valid_date_range(self):
        start, end = validate_date_range("2026-03-01", "2026-03-31")
        assert start == date(2026, 3, 1)
        assert end == date(2026, 3, 31)

    def test_none_dates_allowed(self):
        start, end = validate_date_range(None, None)
        assert start is None
        assert end is None

    def test_single_date_allowed(self):
        start, end = validate_date_range("2026-03-15", None)
        assert start == date(2026, 3, 15)
        assert end is None

    def test_start_after_end_rejected(self):
        with pytest.raises(HTTPException) as exc_info:
            validate_date_range("2026-03-20", "2026-03-10")
        assert exc_info.value.status_code == 400
        assert "cannot be after" in exc_info.value.detail

    @pytest.mark.parametrize(
        "invalid_date",
        [
            "20260315",       # Compact date
            "2026-W11-7",     # ISO week date
            "2026-02-29",     # Invalid calendar (2026 is not a leap year)
            "2026-04-31",     # Invalid calendar (April has 30 days)
            "2026-13-01",     # Month 13 does not exist
            "2026-00-10",     # Month 0 does not exist
            "2026-01-32",     # Day 32 does not exist
            "malformed",      # Non-date string
            "2026/03/15",     # Slash delimiter
            " 2026-03-15 ",   # Whitespace padding
            "",               # Empty string
        ],
    )
    def test_invalid_dates_rejected(self, invalid_date):
        with pytest.raises(HTTPException) as exc_start:
            validate_date_range(invalid_date, None)
        assert exc_start.value.status_code == 400
        assert "Invalid start_date" in exc_start.value.detail

        with pytest.raises(HTTPException) as exc_end:
            validate_date_range(None, invalid_date)
        assert exc_end.value.status_code == 400
        assert "Invalid end_date" in exc_end.value.detail


class TestCurrencyValidation:
    """Test supported currency validation."""

    @pytest.mark.parametrize("curr", ["USD", "EUR", "GBP", "usd", "eur", "gbp", " usd "])
    def test_supported_currencies_accepted(self, curr):
        assert validate_currency(curr) == curr.strip().upper()

    def test_none_or_empty_currency(self):
        assert validate_currency(None) is None
        assert validate_currency("") is None

    @pytest.mark.parametrize("bad_curr", ["CAD", "JPY", "AUD", "CHF", "XYZ", "123", "USDD", "US"])
    def test_unsupported_currencies_rejected(self, bad_curr):
        with pytest.raises(HTTPException) as exc_info:
            validate_currency(bad_curr)
        assert exc_info.value.status_code == 400
        assert "Supported currencies" in exc_info.value.detail


class TestQualityDispositionValidation:
    """Test canonical quality disposition validation."""

    def test_allowed_dispositions_set(self):
        assert ALLOWED_DISPOSITIONS == {"ACCEPTED", "REJECTED", "WARNED", "SKIPPED"}

    @pytest.mark.parametrize(
        "disp",
        ["ACCEPTED", "REJECTED", "WARNED", "SKIPPED", "accepted", "rejected", "warned", "skipped", " Accepted "],
    )
    def test_canonical_dispositions_accepted(self, disp):
        assert validate_disposition(disp) == disp.strip().upper()

    def test_none_or_empty_disposition(self):
        assert validate_disposition(None) is None
        assert validate_disposition("") is None

    @pytest.mark.parametrize("bad_disp", ["LOGGED", "QUARANTINED", "UNKNOWN", "DROP", "123"])
    def test_invalid_dispositions_rejected(self, bad_disp):
        with pytest.raises(HTTPException) as exc_info:
            validate_disposition(bad_disp)
        assert exc_info.value.status_code == 400
        assert "Permitted values" in exc_info.value.detail
