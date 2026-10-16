"""
Unit tests for BankFlow warehouse models and reconciliation report structures.
"""

from decimal import Decimal

from bankflow.warehouse.models import ReconciliationReport, WarehouseLoadingSummary


def test_warehouse_loading_summary_properties():
    summary = WarehouseLoadingSummary(
        batch_id="batch-001",
        branches_loaded=5,
        customers_loaded=25,
        accounts_loaded=40,
        records_inserted=100,
        records_skipped=10,
        status="SUCCEEDED",
        reconciliation_status="RECONCILED",
    )
    assert summary.batch_id == "batch-001"
    assert summary.branches_loaded == 5
    assert summary.customers_loaded == 25
    assert summary.accounts_loaded == 40
    assert summary.records_inserted == 100
    assert summary.records_skipped == 10
    assert summary.total_facts_processed == 110
    assert summary.reconciliation_status == "RECONCILED"
    assert summary.error_summary is None


def test_reconciliation_report_summary_dict():
    report = ReconciliationReport(
        batch_id="batch-002",
        is_reconciled=True,
        extracted_count=100,
        staged_count=100,
        valid_count=95,
        rejected_count=5,
        inserted_count=90,
        skipped_count=5,
        quarantined_count=5,
        staging_value_by_currency_status={("USD", "COMPLETED"): Decimal("1500.50")},
        warehouse_value_by_currency_status={("USD", "COMPLETED"): Decimal("1500.50")},
        discrepancies=[],
    )

    summary_dict = report.to_summary_dict()
    assert summary_dict["batch_id"] == "batch-002"
    assert summary_dict["is_reconciled"] is True
    assert summary_dict["counts"]["staged"] == 100
    assert summary_dict["counts"]["valid"] == 95
    assert summary_dict["counts"]["rejected"] == 5
    assert summary_dict["counts"]["inserted"] == 90
    assert summary_dict["counts"]["skipped"] == 5
    assert summary_dict["counts"]["quarantined"] == 5
    assert summary_dict["discrepancies"] == []


def test_reconciliation_report_unreconciled_with_discrepancies():
    report = ReconciliationReport(
        batch_id="batch-003",
        is_reconciled=False,
        staged_count=100,
        valid_count=90,
        rejected_count=5,
        discrepancies=["Staging count mismatch: staged (100) != valid (90) + rejected (5)."],
    )
    assert report.is_reconciled is False
    assert len(report.discrepancies) == 1
    assert "Staging count mismatch" in report.discrepancies[0]
