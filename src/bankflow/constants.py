"""
BankFlow canonical constants, domain definitions, and data contract definitions.
All components (generator, staging, validator, warehouse, tests) must reference these.
"""

from typing import Final, List, Set

# Transaction Types
TYPE_DEPOSIT: Final[str] = "DEPOSIT"
TYPE_WITHDRAWAL: Final[str] = "WITHDRAWAL"
TYPE_TRANSFER: Final[str] = "TRANSFER"
TYPE_PAYMENT: Final[str] = "PAYMENT"
TYPE_FEE: Final[str] = "FEE"
TYPE_REVERSAL: Final[str] = "REVERSAL"

SUPPORTED_TRANSACTION_TYPES: Final[Set[str]] = {
    TYPE_DEPOSIT,
    TYPE_WITHDRAWAL,
    TYPE_TRANSFER,
    TYPE_PAYMENT,
    TYPE_FEE,
    TYPE_REVERSAL,
}

# Transaction Statuses
STATUS_PENDING: Final[str] = "PENDING"
STATUS_COMPLETED: Final[str] = "COMPLETED"
STATUS_FAILED: Final[str] = "FAILED"
STATUS_REVERSED: Final[str] = "REVERSED"

SUPPORTED_TRANSACTION_STATUSES: Final[Set[str]] = {
    STATUS_PENDING,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_REVERSED,
}

# Transaction Channels
CHANNEL_BRANCH: Final[str] = "BRANCH"
CHANNEL_ATM: Final[str] = "ATM"
CHANNEL_ONLINE: Final[str] = "ONLINE"
CHANNEL_MOBILE: Final[str] = "MOBILE"

SUPPORTED_CHANNELS: Final[Set[str]] = {
    CHANNEL_BRANCH,
    CHANNEL_ATM,
    CHANNEL_ONLINE,
    CHANNEL_MOBILE,
}

# Supported Currencies
CURRENCY_USD: Final[str] = "USD"
CURRENCY_EUR: Final[str] = "EUR"
CURRENCY_GBP: Final[str] = "GBP"

SUPPORTED_CURRENCIES: Final[Set[str]] = {
    CURRENCY_USD,
    CURRENCY_EUR,
    CURRENCY_GBP,
}

# Customer Segments and Statuses
SEGMENT_RETAIL: Final[str] = "RETAIL"
SEGMENT_PREMIUM: Final[str] = "PREMIUM"
SEGMENT_SMALL_BUSINESS: Final[str] = "SMALL_BUSINESS"

SUPPORTED_CUSTOMER_SEGMENTS: Final[Set[str]] = {
    SEGMENT_RETAIL,
    SEGMENT_PREMIUM,
    SEGMENT_SMALL_BUSINESS,
}

CUSTOMER_STATUS_ACTIVE: Final[str] = "ACTIVE"
CUSTOMER_STATUS_INACTIVE: Final[str] = "INACTIVE"

SUPPORTED_CUSTOMER_STATUSES: Final[Set[str]] = {
    CUSTOMER_STATUS_ACTIVE,
    CUSTOMER_STATUS_INACTIVE,
}

# Account Types and Statuses
ACCOUNT_TYPE_CHECKING: Final[str] = "CHECKING"
ACCOUNT_TYPE_SAVINGS: Final[str] = "SAVINGS"

SUPPORTED_ACCOUNT_TYPES: Final[Set[str]] = {
    ACCOUNT_TYPE_CHECKING,
    ACCOUNT_TYPE_SAVINGS,
}

ACCOUNT_STATUS_OPEN: Final[str] = "OPEN"
ACCOUNT_STATUS_CLOSED: Final[str] = "CLOSED"
ACCOUNT_STATUS_RESTRICTED: Final[str] = "RESTRICTED"

SUPPORTED_ACCOUNT_STATUSES: Final[Set[str]] = {
    ACCOUNT_STATUS_OPEN,
    ACCOUNT_STATUS_CLOSED,
    ACCOUNT_STATUS_RESTRICTED,
}

# Batch Lifecycle States
BATCH_STATUS_PENDING: Final[str] = "PENDING"
BATCH_STATUS_RUNNING: Final[str] = "RUNNING"
BATCH_STATUS_SUCCEEDED: Final[str] = "SUCCEEDED"
BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS: Final[str] = "SUCCEEDED_WITH_REJECTIONS"
BATCH_STATUS_FAILED: Final[str] = "FAILED"

SUPPORTED_BATCH_STATUSES: Final[Set[str]] = {
    BATCH_STATUS_PENDING,
    BATCH_STATUS_RUNNING,
    BATCH_STATUS_SUCCEEDED,
    BATCH_STATUS_SUCCEEDED_WITH_REJECTIONS,
    BATCH_STATUS_FAILED,
}

# Stable Data Quality Rule Codes
RULE_FILE_REQUIRED_COLUMN_MISSING: Final[str] = "FILE_REQUIRED_COLUMN_MISSING"
RULE_FILE_HEADER_MISMATCH: Final[str] = "FILE_HEADER_MISMATCH"
RULE_FILE_UNREADABLE: Final[str] = "FILE_UNREADABLE"
RULE_FILE_EMPTY: Final[str] = "FILE_EMPTY"
RULE_BATCH_ALREADY_EXISTS: Final[str] = "BATCH_ALREADY_EXISTS"
RULE_TXN_ID_MISSING: Final[str] = "TXN_ID_MISSING"
RULE_TXN_ID_DUPLICATE: Final[str] = "TXN_ID_DUPLICATE"
RULE_SOURCE_REPLAY_SKIPPED: Final[str] = "SOURCE_REPLAY_SKIPPED"
RULE_ACCOUNT_ID_MISSING: Final[str] = "ACCOUNT_ID_MISSING"
RULE_ACCOUNT_NOT_FOUND: Final[str] = "ACCOUNT_NOT_FOUND"
RULE_AMOUNT_MISSING: Final[str] = "AMOUNT_MISSING"
RULE_AMOUNT_PARSE_ERROR: Final[str] = "AMOUNT_PARSE_ERROR"
RULE_AMOUNT_RULE_VIOLATION: Final[str] = "AMOUNT_RULE_VIOLATION"
RULE_TIMESTAMP_PARSE_ERROR: Final[str] = "TIMESTAMP_PARSE_ERROR"
RULE_TYPE_UNSUPPORTED: Final[str] = "TYPE_UNSUPPORTED"
RULE_STATUS_UNSUPPORTED: Final[str] = "STATUS_UNSUPPORTED"
RULE_CHANNEL_UNSUPPORTED: Final[str] = "CHANNEL_UNSUPPORTED"
RULE_CURRENCY_MISSING: Final[str] = "CURRENCY_MISSING"
RULE_CURRENCY_UNSUPPORTED: Final[str] = "CURRENCY_UNSUPPORTED"
RULE_SOURCE_REFERENCE_MISSING: Final[str] = "SOURCE_REFERENCE_MISSING"
RULE_LOW_DAILY_VOLUME: Final[str] = "LOW_DAILY_VOLUME"
RULE_CONFLICTING_REPLAY_PAYLOAD: Final[str] = "CONFLICTING_REPLAY_PAYLOAD"

# Source File Column Contracts (Order matters for exact CSV header checks)
BRANCHES_COLUMNS: Final[List[str]] = [
    "branch_id",
    "branch_name",
    "region",
]

CUSTOMERS_COLUMNS: Final[List[str]] = [
    "customer_id",
    "customer_segment",
    "created_date",
    "customer_status",
]

ACCOUNTS_COLUMNS: Final[List[str]] = [
    "account_id",
    "customer_id",
    "branch_id",
    "account_type",
    "account_status",
    "opened_date",
    "currency",
]

TRANSACTIONS_COLUMNS: Final[List[str]] = [
    "transaction_id",
    "account_id",
    "transaction_type",
    "amount",
    "currency",
    "transaction_timestamp",
    "status",
    "channel",
    "counterparty_account_id",
    "source_system",
]

ENTITY_SCHEMAS: Final[dict[str, List[str]]] = {
    "branches": BRANCHES_COLUMNS,
    "customers": CUSTOMERS_COLUMNS,
    "accounts": ACCOUNTS_COLUMNS,
    "transactions": TRANSACTIONS_COLUMNS,
}
