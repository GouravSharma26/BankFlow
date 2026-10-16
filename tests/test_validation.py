"""
Unit tests for data-quality validation models, rules, and accounting logic.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from bankflow.constants import (
    CHANNEL_ONLINE,
    CURRENCY_EUR,
    CURRENCY_USD,
    DISPOSITION_ACCEPTED,
    DISPOSITION_REJECTED,
    DISPOSITION_WARNED,
    RULE_ACCOUNT_ID_DUPLICATE,
    RULE_ACCOUNT_ID_MISSING,
    RULE_ACCOUNT_NOT_FOUND,
    RULE_ACCOUNT_STATUS_UNSUPPORTED,
    RULE_ACCOUNT_TYPE_UNSUPPORTED,
    RULE_AMOUNT_MISSING,
    RULE_AMOUNT_PARSE_ERROR,
    RULE_AMOUNT_RULE_VIOLATION,
    RULE_BRANCH_ID_DUPLICATE,
    RULE_BRANCH_ID_MISSING,
    RULE_BRANCH_NAME_MISSING,
    RULE_BRANCH_NOT_FOUND,
    RULE_BRANCH_REGION_MISSING,
    RULE_CHANNEL_UNSUPPORTED,
    RULE_CURRENCY_MISMATCH,
    RULE_CURRENCY_MISSING,
    RULE_CURRENCY_UNSUPPORTED,
    RULE_CUSTOMER_ID_DUPLICATE,
    RULE_CUSTOMER_ID_MISSING,
    RULE_CUSTOMER_NOT_FOUND,
    RULE_CUSTOMER_SEGMENT_UNSUPPORTED,
    RULE_CUSTOMER_STATUS_UNSUPPORTED,
    RULE_DATE_PARSE_ERROR,
    RULE_SOURCE_SYSTEM_MISSING,
    RULE_STATUS_UNSUPPORTED,
    RULE_TIMESTAMP_PARSE_ERROR,
    RULE_TXN_ID_DUPLICATE,
    RULE_TXN_ID_MISSING,
    RULE_TYPE_UNSUPPORTED,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    STATUS_COMPLETED,
    TYPE_DEPOSIT,
)
from bankflow.validation.models import (
    BatchValidationSummary,
    RowValidationOutcome,
    ValidationIssue,
)
from bankflow.validation.validator import ValidationEngine


def test_validation_issue_to_db_tuple():
    issue = ValidationIssue(
        batch_id="batch_001",
        entity_type="TRANSACTION",
        source_file="transactions.csv",
        source_row_number=12,
        source_row_id=101,
        rule_code=RULE_AMOUNT_PARSE_ERROR,
        severity=SEVERITY_ERROR,
        reason="Amount 'INVALID' cannot be parsed.",
        disposition=DISPOSITION_REJECTED,
    )
    tup = issue.to_db_tuple()
    assert tup[0] == issue.issue_id
    assert tup[1] == "batch_001"
    assert tup[2] == "TRANSACTION"
    assert tup[3] == 101
    assert tup[4] == 12
    assert tup[5] == "transactions.csv"
    assert tup[6] == RULE_AMOUNT_PARSE_ERROR
    assert tup[7] == SEVERITY_ERROR
    assert tup[8] == "Amount 'INVALID' cannot be parsed."
    assert tup[9] == DISPOSITION_REJECTED


def test_row_validation_outcome_properties():
    # 1. Clean row
    clean_outcome = RowValidationOutcome(source_row_id=1, source_row_number=1, entity_type="TRANSACTION")
    assert not clean_outcome.is_rejected
    assert not clean_outcome.has_warnings
    assert clean_outcome.disposition == DISPOSITION_ACCEPTED

    # 2. Warning row
    warn_outcome = RowValidationOutcome(
        source_row_id=2,
        source_row_number=2,
        entity_type="TRANSACTION",
        issues=[
            ValidationIssue(
                batch_id="b1",
                entity_type="TRANSACTION",
                source_file="t.csv",
                source_row_number=2,
                rule_code="TEST_WARN",
                severity=SEVERITY_WARNING,
                reason="Minor warning",
            )
        ],
    )
    assert not warn_outcome.is_rejected
    assert warn_outcome.has_warnings
    assert warn_outcome.disposition == DISPOSITION_WARNED

    # 3. Multi-issue rejected row (1 error, 1 warning)
    multi_outcome = RowValidationOutcome(
        source_row_id=3,
        source_row_number=3,
        entity_type="TRANSACTION",
        issues=[
            ValidationIssue(
                batch_id="b1",
                entity_type="TRANSACTION",
                source_file="t.csv",
                source_row_number=3,
                rule_code=RULE_TXN_ID_MISSING,
                severity=SEVERITY_ERROR,
                reason="Missing ID",
            ),
            ValidationIssue(
                batch_id="b1",
                entity_type="TRANSACTION",
                source_file="t.csv",
                source_row_number=3,
                rule_code="TEST_WARN",
                severity=SEVERITY_WARNING,
                reason="Minor warning",
            ),
        ],
    )
    assert multi_outcome.is_rejected
    assert not multi_outcome.has_warnings
    assert multi_outcome.disposition == DISPOSITION_REJECTED


def test_batch_validation_summary_accounting():
    summary = BatchValidationSummary(
        batch_id="batch_accounting_test",
        records_evaluated=10,
        records_valid=7,
        records_rejected=3,
        records_warned=2,
        records_skipped=0,
        total_issues_count=6,
    )
    # Accounting invariant: evaluated == valid + rejected + skipped
    assert summary.records_evaluated == summary.records_valid + summary.records_rejected + summary.records_skipped
    # Notice: 3 rejected rows produced 6 issues, rejected count remains 3!
    assert summary.records_rejected == 3
    assert summary.total_issues_count == 6


def test_validate_transactions_rule_checks():
    engine = ValidationEngine(conn=MagicMock())

    # Build mock staging rows:
    # 0: source_row_id, 1: source_row_number, 2: source_file, 3: transaction_id, 4: account_id,
    # 5: transaction_type, 6: amount_raw, 7: currency, 8: transaction_timestamp_raw,
    # 9: status, 10: channel, 11: counterparty_account_id, 12: source_system, 13: raw_payload
    valid_ts = "2026-03-01T10:00:00+00:00"
    late_ts = "2025-01-01T10:00:00+00:00"  # Valid late-arriving past event

    mock_rows = [
        # 1. Clean valid row
        (1, 1, "txns.csv", "TXN-001", "ACC-01", TYPE_DEPOSIT, "150.00", CURRENCY_USD, valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 2. Missing transaction ID
        (2, 2, "txns.csv", "", "ACC-01", TYPE_DEPOSIT, "150.00", CURRENCY_USD, valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 3. Duplicate transaction ID (first occurrence)
        (3, 3, "txns.csv", "TXN-DUP", "ACC-01", TYPE_DEPOSIT, "150.00", CURRENCY_USD, valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 4. Duplicate transaction ID (second occurrence)
        (4, 4, "txns.csv", "TXN-DUP", "ACC-01", TYPE_DEPOSIT, "150.00", CURRENCY_USD, valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 5. Missing account ID
        (5, 5, "txns.csv", "TXN-005", "", TYPE_DEPOSIT, "150.00", CURRENCY_USD, valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 6. Unknown account reference
        (6, 6, "txns.csv", "TXN-006", "ACC-NONEXISTENT", TYPE_DEPOSIT, "150.00", CURRENCY_USD, valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 7. Unsupported transaction type
        (7, 7, "txns.csv", "TXN-007", "ACC-01", "CRYPTO_TRADE", "150.00", CURRENCY_USD, valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 8. Missing amount
        (8, 8, "txns.csv", "TXN-008", "ACC-01", TYPE_DEPOSIT, "", CURRENCY_USD, valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 9. Non-numeric amount
        (9, 9, "txns.csv", "TXN-009", "ACC-01", TYPE_DEPOSIT, "ONE_HUNDRED", CURRENCY_USD, valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 10. Non-finite amount (NaN)
        (10, 10, "txns.csv", "TXN-010", "ACC-01", TYPE_DEPOSIT, "NaN", CURRENCY_USD, valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 11. Amount rule violation (zero/negative)
        (11, 11, "txns.csv", "TXN-011", "ACC-01", TYPE_DEPOSIT, "-50.00", CURRENCY_USD, valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 12. Missing currency
        (12, 12, "txns.csv", "TXN-012", "ACC-01", TYPE_DEPOSIT, "150.00", "", valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 13. Unsupported currency
        (13, 13, "txns.csv", "TXN-013", "ACC-01", TYPE_DEPOSIT, "150.00", "BITCOIN", valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 14. Missing timestamp
        (14, 14, "txns.csv", "TXN-014", "ACC-01", TYPE_DEPOSIT, "150.00", CURRENCY_USD, "", STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 15. Timestamp lacking timezone offset
        (15, 15, "txns.csv", "TXN-015", "ACC-01", TYPE_DEPOSIT, "150.00", CURRENCY_USD, "2026-03-01 10:00:00", STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 16. Timestamp unparseable text
        (16, 16, "txns.csv", "TXN-016", "ACC-01", TYPE_DEPOSIT, "150.00", CURRENCY_USD, "INVALID_DATE_TEXT", STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 17. Valid late-arriving timestamp (past date)
        (17, 17, "txns.csv", "TXN-017", "ACC-01", TYPE_DEPOSIT, "150.00", CURRENCY_USD, late_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 18. Unsupported status
        (18, 18, "txns.csv", "TXN-018", "ACC-01", TYPE_DEPOSIT, "150.00", CURRENCY_USD, valid_ts, "IN_DISPUTE", CHANNEL_ONLINE, None, "CORE", {}),
        # 19. Unsupported channel
        (19, 19, "txns.csv", "TXN-019", "ACC-01", TYPE_DEPOSIT, "150.00", CURRENCY_USD, valid_ts, STATUS_COMPLETED, "TELEPATHY", None, "CORE", {}),
        # 20. Compound defect row: missing ID, unknown acc, bad amt, bad type, bad curr, bad status, bad channel
        (20, 20, "txns.csv", "", "ACC-UNKNOWN", "BAD_TYPE", "NOT_NUMERIC", "XYZ", valid_ts, "BAD_STATUS", "BAD_CHANNEL", None, "CORE", {}),
        # 21. Currency mismatch (ACC-01 is USD, transaction is EUR)
        (21, 21, "txns.csv", "TXN-021", "ACC-01", TYPE_DEPOSIT, "150.00", CURRENCY_EUR, valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "CORE", {}),
        # 22. Missing source_system
        (22, 22, "txns.csv", "TXN-022", "ACC-01", TYPE_DEPOSIT, "150.00", CURRENCY_USD, valid_ts, STATUS_COMPLETED, CHANNEL_ONLINE, None, "", {}),
    ]

    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = mock_rows

    valid_accounts = {"ACC-01": CURRENCY_USD}
    outcomes = engine._validate_transactions(mock_cur, "test_batch", valid_accounts)

    assert len(outcomes) == 22

    # 1. Clean valid row
    assert not outcomes[0].is_rejected
    assert len(outcomes[0].issues) == 0

    # 2. Missing txn id
    assert outcomes[1].is_rejected
    assert any(i.rule_code == RULE_TXN_ID_MISSING for i in outcomes[1].issues)

    # 3 & 4. Duplicate transaction ID -> both occurrences quarantined
    assert outcomes[2].is_rejected
    assert any(i.rule_code == RULE_TXN_ID_DUPLICATE for i in outcomes[2].issues)
    assert outcomes[3].is_rejected
    assert any(i.rule_code == RULE_TXN_ID_DUPLICATE for i in outcomes[3].issues)

    # 5. Missing account ID
    assert outcomes[4].is_rejected
    assert any(i.rule_code == RULE_ACCOUNT_ID_MISSING for i in outcomes[4].issues)

    # 6. Unknown account reference
    assert outcomes[5].is_rejected
    assert any(i.rule_code == RULE_ACCOUNT_NOT_FOUND for i in outcomes[5].issues)

    # 7. Unsupported type
    assert outcomes[6].is_rejected
    assert any(i.rule_code == RULE_TYPE_UNSUPPORTED for i in outcomes[6].issues)

    # 8. Missing amount
    assert outcomes[7].is_rejected
    assert any(i.rule_code == RULE_AMOUNT_MISSING for i in outcomes[7].issues)

    # 9. Non-numeric amount
    assert outcomes[8].is_rejected
    assert any(i.rule_code == RULE_AMOUNT_PARSE_ERROR for i in outcomes[8].issues)

    # 10. Non-finite amount (NaN)
    assert outcomes[9].is_rejected
    assert any(i.rule_code == RULE_AMOUNT_PARSE_ERROR for i in outcomes[9].issues)

    # 11. Amount violation (negative)
    assert outcomes[10].is_rejected
    assert any(i.rule_code == RULE_AMOUNT_RULE_VIOLATION for i in outcomes[10].issues)

    # 12. Missing currency
    assert outcomes[11].is_rejected
    assert any(i.rule_code == RULE_CURRENCY_MISSING for i in outcomes[11].issues)

    # 13. Unsupported currency
    assert outcomes[12].is_rejected
    assert any(i.rule_code == RULE_CURRENCY_UNSUPPORTED for i in outcomes[12].issues)

    # 14. Missing timestamp
    assert outcomes[13].is_rejected
    assert any(i.rule_code == RULE_TIMESTAMP_PARSE_ERROR for i in outcomes[13].issues)

    # 15. Timestamp lacking timezone offset
    assert outcomes[14].is_rejected
    assert any(i.rule_code == RULE_TIMESTAMP_PARSE_ERROR for i in outcomes[14].issues)

    # 16. Timestamp unparseable text
    assert outcomes[15].is_rejected
    assert any(i.rule_code == RULE_TIMESTAMP_PARSE_ERROR for i in outcomes[15].issues)

    # 17. Valid late-arriving timestamp (past date) -> MUST BE VALID
    assert not outcomes[16].is_rejected
    assert len(outcomes[16].issues) == 0

    # 18. Unsupported status
    assert outcomes[17].is_rejected
    assert any(i.rule_code == RULE_STATUS_UNSUPPORTED for i in outcomes[17].issues)

    # 19. Unsupported channel
    assert outcomes[18].is_rejected
    assert any(i.rule_code == RULE_CHANNEL_UNSUPPORTED for i in outcomes[18].issues)

    # 20. Compound defect row: multiple errors on single row
    assert outcomes[19].is_rejected
    codes = {i.rule_code for i in outcomes[19].issues}
    assert RULE_TXN_ID_MISSING in codes
    assert RULE_ACCOUNT_NOT_FOUND in codes
    assert RULE_TYPE_UNSUPPORTED in codes
    assert RULE_AMOUNT_PARSE_ERROR in codes
    assert RULE_CURRENCY_UNSUPPORTED in codes
    assert RULE_STATUS_UNSUPPORTED in codes
    assert RULE_CHANNEL_UNSUPPORTED in codes
    assert len(outcomes[19].issues) >= 7

    # 21. Currency mismatch
    assert outcomes[20].is_rejected
    assert any(i.rule_code == RULE_CURRENCY_MISMATCH for i in outcomes[20].issues)

    # 22. Missing source system
    assert outcomes[21].is_rejected
    assert any(i.rule_code == RULE_SOURCE_SYSTEM_MISSING for i in outcomes[21].issues)


def test_validate_branches_and_customers_and_accounts():
    engine = ValidationEngine(conn=MagicMock())

    # 1. Branches test
    mock_branch_rows = [
        (1, 1, "branches.csv", "BR-01", "Downtown Branch", "NORTH"),
        (2, 2, "branches.csv", "", "Unnamed Branch", "SOUTH"),  # Missing ID
        (3, 3, "branches.csv", "BR-DUP", "Downtown Dup 1", "NORTH"),  # Duplicate 1
        (4, 4, "branches.csv", "BR-DUP", "Downtown Dup 2", "SOUTH"),  # Duplicate 2
        (5, 5, "branches.csv", "BR-05", "", "NORTH"),  # Missing branch name
        (6, 6, "branches.csv", "BR-06", "Downtown Sub", "   "),  # Missing region (whitespace)
    ]
    cur_branch = MagicMock()
    cur_branch.fetchall.side_effect = [mock_branch_rows, []]  # current batch, then previous batches
    valid_branches, branch_outcomes = engine._validate_branches(cur_branch, "batch_b")
    assert valid_branches == {"BR-01"}
    assert not branch_outcomes[0].is_rejected
    assert branch_outcomes[1].is_rejected
    assert any(i.rule_code == RULE_BRANCH_ID_MISSING for i in branch_outcomes[1].issues)
    assert branch_outcomes[2].is_rejected
    assert any(i.rule_code == RULE_BRANCH_ID_DUPLICATE for i in branch_outcomes[2].issues)
    assert branch_outcomes[3].is_rejected
    assert any(i.rule_code == RULE_BRANCH_ID_DUPLICATE for i in branch_outcomes[3].issues)
    assert branch_outcomes[4].is_rejected
    assert any(i.rule_code == RULE_BRANCH_NAME_MISSING for i in branch_outcomes[4].issues)
    assert branch_outcomes[5].is_rejected
    assert any(i.rule_code == RULE_BRANCH_REGION_MISSING for i in branch_outcomes[5].issues)

    # 2. Customers test
    mock_cust_rows = [
        (1, 1, "customers.csv", "CUST-01", "RETAIL", "2026-01-01", "ACTIVE"),
        (2, 2, "customers.csv", "", "RETAIL", "2026-01-01", "ACTIVE"),  # Missing ID
        (3, 3, "customers.csv", "CUST-03", "VIP_ALIEN", "2026-01-01", "ACTIVE"),  # Bad segment
        (4, 4, "customers.csv", "CUST-04", "RETAIL", "2026-01-01", "FROZEN_UNKNOWN"),  # Bad status
        (5, 5, "customers.csv", "CUST-DUP", "RETAIL", "2026-01-01", "ACTIVE"),  # Duplicate 1
        (6, 6, "customers.csv", "CUST-DUP", "RETAIL", "2026-01-01", "ACTIVE"),  # Duplicate 2
        (7, 7, "customers.csv", "CUST-07", "RETAIL", "2026/01/01", "ACTIVE"),  # Malformed date
        (8, 8, "customers.csv", "CUST-08", "RETAIL", "", "ACTIVE"),  # Missing date
    ]
    cur_cust = MagicMock()
    cur_cust.fetchall.side_effect = [mock_cust_rows, []]
    valid_customers, cust_outcomes = engine._validate_customers(cur_cust, "batch_c")
    assert valid_customers == {"CUST-01"}
    assert not cust_outcomes[0].is_rejected
    assert cust_outcomes[1].is_rejected
    assert any(i.rule_code == RULE_CUSTOMER_ID_MISSING for i in cust_outcomes[1].issues)
    assert cust_outcomes[2].is_rejected
    assert any(i.rule_code == RULE_CUSTOMER_SEGMENT_UNSUPPORTED for i in cust_outcomes[2].issues)
    assert cust_outcomes[3].is_rejected
    assert any(i.rule_code == RULE_CUSTOMER_STATUS_UNSUPPORTED for i in cust_outcomes[3].issues)
    assert cust_outcomes[4].is_rejected
    assert any(i.rule_code == RULE_CUSTOMER_ID_DUPLICATE for i in cust_outcomes[4].issues)
    assert cust_outcomes[5].is_rejected
    assert any(i.rule_code == RULE_CUSTOMER_ID_DUPLICATE for i in cust_outcomes[5].issues)
    assert cust_outcomes[6].is_rejected
    assert any(i.rule_code == RULE_DATE_PARSE_ERROR for i in cust_outcomes[6].issues)
    assert cust_outcomes[7].is_rejected
    assert any(i.rule_code == RULE_DATE_PARSE_ERROR for i in cust_outcomes[7].issues)

    # 3. Accounts test
    mock_acc_rows = [
        (1, 1, "accounts.csv", "ACC-01", "CUST-01", "BR-01", "CHECKING", "OPEN", "2026-01-01", "USD"),
        (2, 2, "accounts.csv", "", "CUST-01", "BR-01", "CHECKING", "OPEN", "2026-01-01", "USD"),  # Missing ID
        (3, 3, "accounts.csv", "ACC-03", "CUST-UNKNOWN", "BR-01", "CHECKING", "OPEN", "2026-01-01", "USD"),  # Bad customer
        (4, 4, "accounts.csv", "ACC-04", "CUST-01", "BR-UNKNOWN", "CHECKING", "OPEN", "2026-01-01", "USD"),  # Bad branch
        (5, 5, "accounts.csv", "ACC-05", "CUST-01", "BR-01", "INVESTMENT_FUND", "OPEN", "2026-01-01", "USD"),  # Bad type
        (6, 6, "accounts.csv", "ACC-06", "CUST-01", "BR-01", "CHECKING", "DORMANT_UNKNOWN", "2026-01-01", "USD"),  # Bad status
        (7, 7, "accounts.csv", "ACC-07", "CUST-01", "BR-01", "CHECKING", "OPEN", "2026-01-01", ""),  # Missing currency
        (8, 8, "accounts.csv", "ACC-08", "CUST-01", "BR-01", "CHECKING", "OPEN", "2026-01-01", "XYZ_CRYPTO"),  # Bad currency
        (9, 9, "accounts.csv", "ACC-DUP", "CUST-01", "BR-01", "CHECKING", "OPEN", "2026-01-01", "USD"),  # Duplicate 1
        (10, 10, "accounts.csv", "ACC-DUP", "CUST-01", "BR-01", "CHECKING", "OPEN", "2026-01-01", "USD"),  # Duplicate 2
        (11, 11, "accounts.csv", "ACC-11", "CUST-01", "BR-01", "CHECKING", "OPEN", "01-01-2026", "USD"),  # Malformed date
        (12, 12, "accounts.csv", "ACC-12", "CUST-01", "BR-01", "CHECKING", "OPEN", "   ", "USD"),  # Missing date
    ]
    cur_acc = MagicMock()
    cur_acc.fetchall.side_effect = [mock_acc_rows, []]
    valid_accounts, acc_outcomes = engine._validate_accounts(
        cur_acc, "batch_a", valid_customer_ids={"CUST-01"}, valid_branch_ids={"BR-01"}
    )
    assert valid_accounts == {"ACC-01": "USD"}
    assert not acc_outcomes[0].is_rejected
    assert acc_outcomes[1].is_rejected
    assert any(i.rule_code == RULE_ACCOUNT_ID_MISSING for i in acc_outcomes[1].issues)
    assert acc_outcomes[2].is_rejected
    assert any(i.rule_code == RULE_CUSTOMER_NOT_FOUND for i in acc_outcomes[2].issues)
    assert acc_outcomes[3].is_rejected
    assert any(i.rule_code == RULE_BRANCH_NOT_FOUND for i in acc_outcomes[3].issues)
    assert acc_outcomes[4].is_rejected
    assert any(i.rule_code == RULE_ACCOUNT_TYPE_UNSUPPORTED for i in acc_outcomes[4].issues)
    assert acc_outcomes[5].is_rejected
    assert any(i.rule_code == RULE_ACCOUNT_STATUS_UNSUPPORTED for i in acc_outcomes[5].issues)
    assert acc_outcomes[6].is_rejected
    assert any(i.rule_code == RULE_CURRENCY_MISSING for i in acc_outcomes[6].issues)
    assert acc_outcomes[7].is_rejected
    assert any(i.rule_code == RULE_CURRENCY_UNSUPPORTED for i in acc_outcomes[7].issues)
    assert acc_outcomes[8].is_rejected
    assert any(i.rule_code == RULE_ACCOUNT_ID_DUPLICATE for i in acc_outcomes[8].issues)
    assert acc_outcomes[9].is_rejected
    assert any(i.rule_code == RULE_ACCOUNT_ID_DUPLICATE for i in acc_outcomes[9].issues)
    assert acc_outcomes[10].is_rejected
    assert any(i.rule_code == RULE_DATE_PARSE_ERROR for i in acc_outcomes[10].issues)
    assert acc_outcomes[11].is_rejected
    assert any(i.rule_code == RULE_DATE_PARSE_ERROR for i in acc_outcomes[11].issues)
