"""
Input validation and whitelisting helpers for the BankFlow Reporting API.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional, Set
from fastapi import HTTPException, status

ISO_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")

ALLOWED_STATUSES: Set[str] = {"COMPLETED", "PENDING", "FAILED", "REVERSED"}
ALLOWED_TRANSACTION_TYPES: Set[str] = {"DEPOSIT", "WITHDRAWAL", "TRANSFER", "PAYMENT", "FEE", "REVERSAL"}
ALLOWED_CHANNELS: Set[str] = {"BRANCH", "ATM", "ONLINE", "MOBILE"}
ALLOWED_ENTITY_TYPES: Set[str] = {"BRANCH", "CUSTOMER", "ACCOUNT", "TRANSACTION"}
ALLOWED_SEVERITIES: Set[str] = {"ERROR", "WARNING", "INFO"}
ALLOWED_DISPOSITIONS: Set[str] = {"REJECTED", "QUARANTINED", "SKIPPED", "LOGGED"}
ALLOWED_RECONCILIATION_STATUSES: Set[str] = {"RECONCILED", "UNRECONCILED", "DISCREPANCY_DETECTED"}


def validate_currency(currency: Optional[str]) -> Optional[str]:
    if not currency:
        return None
    curr = currency.strip().upper()
    if not ISO_CURRENCY_PATTERN.match(curr):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid currency '{currency}'. Expected 3-letter uppercase ISO currency code (e.g. USD, EUR, GBP).",
        )
    return curr


def validate_status(status_val: Optional[str]) -> Optional[str]:
    if not status_val:
        return None
    val = status_val.strip().upper()
    if val not in ALLOWED_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status '{status_val}'. Permitted values: {sorted(ALLOWED_STATUSES)}.",
        )
    return val


def validate_transaction_type(type_val: Optional[str]) -> Optional[str]:
    if not type_val:
        return None
    val = type_val.strip().upper()
    if val not in ALLOWED_TRANSACTION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid transaction type '{type_val}'. Permitted values: {sorted(ALLOWED_TRANSACTION_TYPES)}.",
        )
    return val


def validate_channel(channel: Optional[str]) -> Optional[str]:
    if not channel:
        return None
    val = channel.strip().upper()
    if val not in ALLOWED_CHANNELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel '{channel}'. Permitted values: {sorted(ALLOWED_CHANNELS)}.",
        )
    return val


def validate_entity_type(entity: Optional[str]) -> Optional[str]:
    if not entity:
        return None
    val = entity.strip().upper()
    if val not in ALLOWED_ENTITY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity type '{entity}'. Permitted values: {sorted(ALLOWED_ENTITY_TYPES)}.",
        )
    return val


def validate_severity(severity: Optional[str]) -> Optional[str]:
    if not severity:
        return None
    val = severity.strip().upper()
    if val not in ALLOWED_SEVERITIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid severity '{severity}'. Permitted values: {sorted(ALLOWED_SEVERITIES)}.",
        )
    return val


def validate_disposition(disposition: Optional[str]) -> Optional[str]:
    if not disposition:
        return None
    val = disposition.strip().upper()
    if val not in ALLOWED_DISPOSITIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid disposition '{disposition}'. Permitted values: {sorted(ALLOWED_DISPOSITIONS)}.",
        )
    return val


def validate_reconciliation_status(recon_status: Optional[str]) -> Optional[str]:
    if not recon_status:
        return None
    val = recon_status.strip().upper()
    if val not in ALLOWED_RECONCILIATION_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid reconciliation status '{recon_status}'. Permitted values: {sorted(ALLOWED_RECONCILIATION_STATUSES)}.",
        )
    return val


def validate_date_range(start_date_str: Optional[str], end_date_str: Optional[str]) -> tuple[Optional[date], Optional[date]]:
    start_d = None
    end_d = None

    if start_date_str:
        try:
            start_d = date.fromisoformat(start_date_str.strip())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid start_date '{start_date_str}'. Expected format: YYYY-MM-DD.",
            )

    if end_date_str:
        try:
            end_d = date.fromisoformat(end_date_str.strip())
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid end_date '{end_date_str}'. Expected format: YYYY-MM-DD.",
            )

    if start_d and end_d and start_d > end_d:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"start_date ({start_d}) cannot be after end_date ({end_d}).",
        )

    return start_d, end_d
