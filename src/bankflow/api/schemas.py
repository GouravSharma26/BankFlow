"""
Pydantic schemas for the BankFlow Reporting API.
Enforces strict typing, monetary precision, and documented API contracts.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(..., description="Service health status ('healthy' or 'degraded')")
    service: str = Field(default="bankflow-reporting-api", description="Service name")
    version: str = Field(default="0.1.0", description="API version")
    database: str = Field(..., description="Database connection status ('connected' or 'unavailable')")


class OverviewCurrencySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str = Field(..., description="ISO currency code")
    total_transactions: int = Field(..., description="Total transactions processed")
    completed_transactions: int = Field(..., description="Completed transaction count")
    gross_transaction_amount: str = Field(..., description="Total gross event amount (positive Decimal)")
    completed_gross_amount: str = Field(..., description="Gross amount of completed transactions")
    acceptance_rate_pct: str = Field(..., description="Completed transactions as a percentage of total")
    active_accounts: int = Field(..., description="Distinct accounts transacted")
    active_customers: int = Field(..., description="Distinct customers transacted")


class OverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currencies: List[str] = Field(..., description="List of currencies present in warehouse")
    earliest_date: Optional[str] = Field(None, description="Earliest transaction date (YYYY-MM-DD)")
    latest_date: Optional[str] = Field(None, description="Latest transaction date (YYYY-MM-DD)")
    metrics_by_currency: List[OverviewCurrencySummary] = Field(..., description="Portfolio metrics grouped strictly by currency")
    total_batches: int = Field(..., description="Total ETL batches recorded in monitoring")
    latest_batch_status: Optional[str] = Field(None, description="Status of the most recent batch run")
    total_quality_issues: int = Field(..., description="Total data quality issue records")
    total_quarantined_records: int = Field(..., description="Total rejected records quarantined")


class DailyTrendItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_key: int = Field(..., description="Surrogate date dimension key (YYYYMMDD)")
    reporting_date: str = Field(..., description="Reporting calendar date (YYYY-MM-DD in UTC)")
    year_number: int = Field(..., description="Calendar year")
    month_number: int = Field(..., description="Calendar month (1-12)")
    month_name: str = Field(..., description="Month name (e.g. 'March')")
    day_name: str = Field(..., description="Day of week name (e.g. 'Sunday')")
    is_weekend: bool = Field(..., description="Whether date falls on Saturday or Sunday")
    currency: str = Field(..., description="ISO currency code")
    total_transaction_count: int = Field(..., description="Total transaction events on date")
    completed_transaction_count: int = Field(..., description="Completed transactions on date")
    pending_transaction_count: int = Field(..., description="Pending transactions on date")
    failed_transaction_count: int = Field(..., description="Failed transactions on date")
    reversed_transaction_count: int = Field(..., description="Reversed transactions on date")
    active_accounts: int = Field(..., description="Distinct accounts active on date")
    active_customers: int = Field(..., description="Distinct customers active on date")
    gross_transaction_amount: str = Field(..., description="Total gross transaction amount")
    completed_gross_amount: str = Field(..., description="Completed gross transaction amount")


class DepositWithdrawalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_key: int = Field(..., description="Surrogate date dimension key")
    reporting_date: str = Field(..., description="Reporting calendar date (YYYY-MM-DD in UTC)")
    currency: str = Field(..., description="ISO currency code")
    deposit_count: int = Field(..., description="Total deposit events")
    deposit_gross_amount: str = Field(..., description="Total gross deposit value")
    completed_deposit_count: int = Field(..., description="Completed deposit events")
    completed_deposit_gross_amount: str = Field(..., description="Completed gross deposit value")
    withdrawal_count: int = Field(..., description="Total withdrawal events")
    withdrawal_gross_amount: str = Field(..., description="Total gross withdrawal value")
    completed_withdrawal_count: int = Field(..., description="Completed withdrawal events")
    completed_withdrawal_gross_amount: str = Field(..., description="Completed gross withdrawal value")
    reversal_count: int = Field(..., description="Total reversal adjustment events")
    reversal_gross_amount: str = Field(..., description="Total gross reversal value")
    deposit_value_share_pct: str = Field(..., description="Completed deposit value as % of total completed deposit+withdrawal value")
    withdrawal_value_share_pct: str = Field(..., description="Completed withdrawal value as % of total completed deposit+withdrawal value")


class BranchChannelItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    region: str = Field(..., description="Geographic administrative region")
    branch_id: str = Field(..., description="Branch natural identifier")
    branch_name: str = Field(..., description="Branch descriptive name")
    channel: str = Field(..., description="Transaction channel (BRANCH, ATM, ONLINE, MOBILE)")
    currency: str = Field(..., description="ISO currency code")
    total_transaction_count: int = Field(..., description="Total transaction events")
    completed_transaction_count: int = Field(..., description="Completed transaction events")
    distinct_accounts: int = Field(..., description="Distinct accounts serviced")
    distinct_customers: int = Field(..., description="Distinct customers serviced")
    gross_transaction_amount: str = Field(..., description="Total gross event amount")
    completed_gross_amount: str = Field(..., description="Completed gross event amount")


class TypeMixItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_type_code: str = Field(..., description="Standard transaction type code")
    transaction_type_name: str = Field(..., description="Display name for transaction type")
    transaction_family: str = Field(..., description="Accounting classification family")
    currency: str = Field(..., description="ISO currency code")
    total_transaction_count: int = Field(..., description="Total events for this type")
    completed_transaction_count: int = Field(..., description="Completed events for this type")
    failed_transaction_count: int = Field(..., description="Failed events for this type")
    pending_transaction_count: int = Field(..., description="Pending events for this type")
    reversed_transaction_count: int = Field(..., description="Reversed events for this type")
    gross_transaction_amount: str = Field(..., description="Total gross event amount")
    completed_gross_amount: str = Field(..., description="Completed gross event amount")
    event_share_pct: str = Field(..., description="Share of total portfolio event count")
    value_share_pct: str = Field(..., description="Share of total portfolio gross event value")


class QualitySummaryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_code: str = Field(..., description="Validation rule code")
    severity: str = Field(..., description="Issue severity (ERROR, WARNING, INFO)")
    disposition: str = Field(..., description="Disposition outcome (ACCEPTED, REJECTED, WARNED, SKIPPED)")
    issue_count: int = Field(..., description="Individual quality issue records flagged")
    affected_source_rows: int = Field(..., description="Distinct source rows affected (zero double counting)")
    affected_batches: int = Field(..., description="Distinct batches impacted")


class BatchExecutionItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str = Field(..., description="ETL batch identifier")
    source_name: str = Field(..., description="Source dataset origin name")
    started_at: Optional[str] = Field(None, description="Batch execution start timestamp")
    completed_at: Optional[str] = Field(None, description="Batch execution completion timestamp")
    duration_seconds: Optional[float] = Field(None, description="Elapsed batch duration in seconds")
    status: str = Field(..., description="Batch lifecycle status")
    records_extracted: int = Field(..., description="Total records parsed from source files")
    records_staged: int = Field(..., description="Total records staged into database")
    records_valid: int = Field(..., description="Valid records meeting data contract")
    records_rejected: int = Field(..., description="Rejected records failing data contract")
    records_inserted: int = Field(..., description="New transaction facts loaded to warehouse")
    records_updated: int = Field(..., description="Warehouse records updated")
    records_skipped: int = Field(..., description="Identical duplicate replays skipped")
    rejection_rate_pct: str = Field(..., description="Rejected rows as a percentage of staged rows")
    reconciliation_status: Optional[str] = Field(None, description="Source-to-target reconciliation outcome")
    error_summary: Optional[str] = Field(None, description="Error diagnostics if failed")


class QuarantineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str = Field(..., description="ETL batch identifier")
    entity_type: str = Field(..., description="Entity type quarantined (TRANSACTION, CUSTOMER, etc.)")
    primary_rule_code: str = Field(..., description="Primary rule code triggering quarantine")
    quarantined_rows: int = Field(..., description="Total quarantined rows")
    recorded_issue_count: int = Field(..., description="Total defects on quarantined rows")
    first_quarantined_at: Optional[str] = Field(None, description="Earliest quarantine timestamp")
    last_quarantined_at: Optional[str] = Field(None, description="Latest quarantine timestamp")


class TransactionDetailItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str = Field(..., description="Source business transaction identifier")
    source_system: str = Field(..., description="Originating source system")
    account_id: str = Field(..., description="Associated account identifier")
    customer_id: str = Field(..., description="Associated customer identifier")
    branch_id: str = Field(..., description="Servicing branch identifier")
    branch_name: str = Field(..., description="Servicing branch name")
    region: str = Field(..., description="Branch geographical region")
    transaction_type: str = Field(..., description="Standard transaction type code")
    type_name: str = Field(..., description="Descriptive transaction type name")
    transaction_family: str = Field(..., description="Accounting classification family")
    amount: str = Field(..., description="Positive gross transaction amount")
    currency: str = Field(..., description="ISO currency code")
    status: str = Field(..., description="Transaction status (COMPLETED, PENDING, FAILED, REVERSED)")
    channel: str = Field(..., description="Channel (BRANCH, ATM, ONLINE, MOBILE)")
    transaction_timestamp: str = Field(..., description="ISO 8601 transaction timestamp")
    reporting_date: str = Field(..., description="Reporting calendar date (YYYY-MM-DD)")
    batch_id: str = Field(..., description="Loading batch identifier")
    loaded_at: Optional[str] = Field(None, description="Warehouse ingestion timestamp")


class PaginatedTransactionsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[TransactionDetailItem] = Field(..., description="List of transaction records")
    total: int = Field(..., description="Total matching transactions")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Page size limit")
    total_pages: int = Field(..., description="Total available pages")


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: str = Field(..., description="Human-readable error explanation")
    error_code: Optional[str] = Field(None, description="Machine-readable error category")
