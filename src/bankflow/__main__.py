"""
BankFlow CLI entry point.
Provides commands for database initialization, data generation, staging ingestion, and batch inspection.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from bankflow.config import get_settings
from bankflow.db import check_connection, get_connection
from bankflow.generator.defects import DefectConfig
from bankflow.generator.generator import SyntheticDataGenerator
from bankflow.staging.loader import StagingLoader
from bankflow.staging.schema import init_staging_schema
from bankflow.validation.schema import init_validation_schema
from bankflow.validation.validator import ValidationEngine
from bankflow.warehouse.loader import WarehouseLoader
from bankflow.warehouse.reconciliation import ReconciliationEngine
from bankflow.warehouse.schema import init_warehouse_schema


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """BankFlow — Banking Transaction Batch ETL & Analytics Platform."""
    pass


@cli.command("test-connection")
@click.option("--test-db", is_flag=True, help="Test connection to the dedicated test database.")
def test_conn_cmd(test_db: bool):
    """Verify database connectivity without logging credentials."""
    settings = get_settings()
    db_config = settings.test_db if test_db else settings.db
    target_type = "test" if test_db else "primary"

    click.echo(f"Testing connectivity to {target_type} database '{db_config.name}' on {db_config.host}:{db_config.port}...")
    success, msg = check_connection(db_config)
    if success:
        click.secho(f"[OK] {msg}", fg="green")
    else:
        click.secho(f"[ERROR] {msg}", fg="red")
        sys.exit(1)


@cli.command("init-db")
@click.option("--test-db", is_flag=True, help="Initialize the dedicated test database instead of primary.")
def init_db_cmd(test_db: bool):
    """Initialize PostgreSQL staging, monitoring, and quarantine schemas and tables."""
    settings = get_settings()
    db_config = settings.test_db if test_db else settings.db
    target_type = "test" if test_db else "primary"

    click.echo(f"Connecting to {target_type} database '{db_config.name}' on {db_config.host}:{db_config.port}...")
    try:
        with get_connection(db_config) as conn:
            init_staging_schema(conn)
            init_validation_schema(conn)
            init_warehouse_schema(conn)
        click.secho(f"[OK] Successfully initialized staging, monitoring, quarantine, and warehouse schemas in '{db_config.name}'.", fg="green")
    except Exception as ex:
        click.secho(f"[ERROR] Database initialization failed: {ex}", fg="red")
        sys.exit(1)



@cli.command("generate")
@click.option("--output-dir", "-o", default="data/samples", show_default=True, type=click.Path(path_type=Path), help="Directory to save CSV files.")
@click.option("--seed", "-s", default=42, show_default=True, type=int, help="Random seed for reproducible generation.")
@click.option("--branches", default=5, show_default=True, type=int, help="Number of branches.")
@click.option("--customers", default=25, show_default=True, type=int, help="Number of customers.")
@click.option("--accounts", default=40, show_default=True, type=int, help="Number of accounts.")
@click.option("--transactions", default=100, show_default=True, type=int, help="Number of transactions.")
@click.option("--start-date", default="2026-01-01", show_default=True, help="Start date (YYYY-MM-DD) for transaction event generation.")
@click.option("--end-date", default="2026-03-31", show_default=True, help="End date (YYYY-MM-DD) inclusive for transaction event generation.")
@click.option("--with-defects", is_flag=True, help="Inject standard test defect scenarios for data quality testing.")
def generate_cmd(
    output_dir: Path,
    seed: int,
    branches: int,
    customers: int,
    accounts: int,
    transactions: int,
    start_date: str,
    end_date: str,
    with_defects: bool,
):
    """Generate synthetic CSV files with fixed seed and optional defect cases."""
    from datetime import datetime
    try:
        s_dt = datetime.strptime(start_date, "%Y-%m-%d")
        e_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if e_dt < s_dt:
            click.secho(f"[ERROR] End date ({end_date}) cannot be before start date ({start_date}).", fg="red")
            sys.exit(1)
    except ValueError as ex:
        click.secho(f"[ERROR] Invalid date format (expected YYYY-MM-DD): {ex}", fg="red")
        sys.exit(1)

    defect_config = DefectConfig.standard_test_defects() if with_defects else DefectConfig.clean()
    generator = SyntheticDataGenerator(seed=seed, defect_config=defect_config)

    click.echo(f"Generating synthetic dataset (seed={seed}, defects={with_defects}, {start_date} to {end_date})...")
    files = generator.export_all(
        output_dir=output_dir,
        num_branches=branches,
        num_customers=customers,
        num_accounts=accounts,
        num_transactions=transactions,
        start_date=start_date,
        end_date=end_date,
    )

    click.secho(f"[OK] Generated {len(files)} CSV files in {output_dir}:", fg="green")
    for entity, path in files.items():
        click.echo(f"  - {entity}: {path}")


@cli.command("stage")
@click.option("--input-dir", "-i", default="data/samples", show_default=True, type=click.Path(exists=True, path_type=Path), help="Directory containing CSV files.")
@click.option("--batch-id", help="Optional explicit batch identifier.")
@click.option("--validate", is_flag=True, help="Automatically run validation immediately after staging.")
@click.option("--test-db", is_flag=True, help="Ingest into the test database instead of primary.")
def stage_cmd(input_dir: Path, batch_id: Optional[str], validate: bool, test_db: bool):
    """Ingest CSV files from a dataset directory into PostgreSQL staging tables."""
    settings = get_settings()
    db_config = settings.test_db if test_db else settings.db

    try:
        with get_connection(db_config) as conn:
            loader = StagingLoader(conn)
            click.echo(f"Starting staging ingestion from {input_dir}...")
            result = loader.ingest_dataset_directory(input_dir, batch_id=batch_id)

            if result["status"] == "SUCCEEDED":
                b_id = result["batch_id"]
                click.secho(f"[OK] Batch '{b_id}' staging succeeded!", fg="green")
                click.echo(f"  Extracted records: {result['records_extracted']}")
                click.echo(f"  Staged records:    {result['records_staged']}")
                for entity, count in result.get("entity_counts", {}).items():
                    click.echo(f"    - {entity}: {count}")

                if validate:
                    click.echo(f"\nRunning validation engine on batch '{b_id}'...")
                    engine = ValidationEngine(conn)
                    summary = engine.validate_batch(b_id)
                    status_color = "green" if summary.batch_status == "SUCCEEDED" else "yellow"
                    click.secho(f"[{summary.batch_status}] Validation complete for batch '{b_id}'", fg=status_color)
                    click.echo(f"  Evaluated: {summary.records_evaluated} | Valid: {summary.records_valid} | Rejected: {summary.records_rejected}")
                    if summary.issues_by_rule:
                        click.echo("  Issues by rule:")
                        for r_code, r_cnt in sorted(summary.issues_by_rule.items()):
                            click.echo(f"    - {r_code}: {r_cnt}")
            else:
                click.secho(f"[ERROR] Batch '{result['batch_id']}' failed: [{result.get('error_code')}] {result.get('error_message')}", fg="red")
                sys.exit(1)

    except Exception as ex:
        click.secho(f"[ERROR] Staging ingestion failed: {ex}", fg="red")
        sys.exit(1)


@cli.command("validate")
@click.argument("batch_id")
@click.option("--test-db", is_flag=True, help="Validate batch in test database instead of primary.")
def validate_cmd(batch_id: str, test_db: bool):
    """Validate staged records for a batch, record data-quality issues, and quarantine rejected rows."""
    settings = get_settings()
    db_config = settings.test_db if test_db else settings.db

    try:
        with get_connection(db_config) as conn:
            engine = ValidationEngine(conn)
            click.echo(f"Validating staged records for batch '{batch_id}'...")
            summary = engine.validate_batch(batch_id)

            status_color = "green" if summary.batch_status == "SUCCEEDED" else "yellow"
            click.secho(f"[{summary.batch_status}] Validation completed for batch '{batch_id}'", fg=status_color)
            click.echo(f"  Records evaluated: {summary.records_evaluated}")
            click.echo(f"  Records valid:     {summary.records_valid}")
            click.echo(f"  Records rejected:  {summary.records_rejected}")
            click.echo(f"  Total issues:      {summary.total_issues_count}")
            if summary.issues_by_rule:
                click.echo("  Issues by rule code:")
                for rule, count in sorted(summary.issues_by_rule.items()):
                    click.echo(f"    - {rule}: {count}")
    except Exception as ex:
        click.secho(f"[ERROR] Validation failed: {ex}", fg="red")
        sys.exit(1)


@cli.command("load")
@click.argument("batch_id")
@click.option("--test-db", is_flag=True, help="Load batch into test database warehouse instead of primary.")
def load_cmd(batch_id: str, test_db: bool):
    """Load validated staging records for a batch into the dimensional warehouse."""
    settings = get_settings()
    db_config = settings.test_db if test_db else settings.db

    try:
        with get_connection(db_config) as conn:
            loader = WarehouseLoader(conn)
            click.echo(f"Loading validated records for batch '{batch_id}' into warehouse...")
            summary = loader.load_batch(batch_id)

            click.secho(f"[OK] Warehouse loading completed for batch '{batch_id}'!", fg="green")
            click.echo(f"  Dimensions loaded:")
            click.echo(f"    - Branches:  {summary.branches_loaded}")
            click.echo(f"    - Customers: {summary.customers_loaded}")
            click.echo(f"    - Accounts:  {summary.accounts_loaded}")
            click.echo(f"  Fact Transactions:")
            click.echo(f"    - Inserted:  {summary.records_inserted}")
            click.echo(f"    - Skipped:   {summary.records_skipped} (idempotent replay)")
            recon_color = "green" if summary.reconciliation_status == "RECONCILED" else "red"
            click.secho(f"  Reconciliation: {summary.reconciliation_status}", fg=recon_color)
    except Exception as ex:
        click.secho(f"[ERROR] Warehouse loading failed: {ex}", fg="red")
        sys.exit(1)


@cli.command("reconcile")
@click.argument("batch_id")
@click.option("--test-db", is_flag=True, help="Run reconciliation in test database instead of primary.")
def reconcile_cmd(batch_id: str, test_db: bool):
    """Audit count and monetary value reconciliation across staging, validation, and warehouse."""
    settings = get_settings()
    db_config = settings.test_db if test_db else settings.db

    try:
        with get_connection(db_config) as conn:
            engine = ReconciliationEngine(conn)
            click.echo(f"Auditing reconciliation for batch '{batch_id}'...")
            report = engine.reconcile_batch(batch_id)

            if report.is_reconciled:
                click.secho(f"[RECONCILED] Batch '{batch_id}' is fully reconciled across all layers!", fg="green")
            else:
                click.secho(f"[UNRECONCILED] Discrepancies detected for batch '{batch_id}':", fg="red")
                for d in report.discrepancies:
                    click.echo(f"  - {d}")

            click.echo("  Count Audit:")
            click.echo(f"    Extracted:    {report.extracted_count}")
            click.echo(f"    Staged:       {report.staged_count}")
            click.echo(f"    Valid:        {report.valid_count}")
            click.echo(f"    Rejected:     {report.rejected_count}")
            click.echo(f"    Inserted:     {report.inserted_count}")
            click.echo(f"    Skipped:      {report.skipped_count}")
            click.echo(f"    Quarantined:  {report.quarantined_count}")
    except Exception as ex:
        click.secho(f"[ERROR] Reconciliation check failed: {ex}", fg="red")
        sys.exit(1)


@cli.command("run")
@click.option("--input-dir", "-i", default="data/samples", show_default=True, type=click.Path(exists=True, path_type=Path), help="Directory containing CSV files.")
@click.option("--batch-id", help="Optional explicit batch identifier.")
@click.option("--test-db", is_flag=True, help="Run ETL pipeline in test database instead of primary.")
def run_pipeline_cmd(input_dir: Path, batch_id: Optional[str], test_db: bool):
    """Run full batch ETL pipeline: stage -> validate -> load -> reconcile."""
    settings = get_settings()
    db_config = settings.test_db if test_db else settings.db

    try:
        with get_connection(db_config) as conn:
            # 1. Staging
            loader = StagingLoader(conn)
            click.echo(f"1. Ingesting staging records from {input_dir}...")
            result = loader.ingest_dataset_directory(input_dir, batch_id=batch_id)
            if result["status"] != "SUCCEEDED":
                click.secho(f"[ERROR] Staging failed: [{result.get('error_code')}] {result.get('error_message')}", fg="red")
                sys.exit(1)
            b_id = result["batch_id"]
            click.secho(f"   [OK] Staged {result['records_staged']} records (batch: {b_id})", fg="green")

            # 2. Validation
            click.echo(f"2. Validating staged records for batch '{b_id}'...")
            v_engine = ValidationEngine(conn)
            v_summary = v_engine.validate_batch(b_id)
            v_color = "green" if v_summary.batch_status == "SUCCEEDED" else "yellow"
            click.secho(f"   [{v_summary.batch_status}] Valid: {v_summary.records_valid} | Rejected: {v_summary.records_rejected}", fg=v_color)

            # 3. Warehouse Loading
            click.echo(f"3. Loading valid records into dimensional warehouse...")
            wh_loader = WarehouseLoader(conn)
            wh_summary = wh_loader.load_batch(b_id)
            click.secho(f"   [OK] Inserted {wh_summary.records_inserted} facts | Skipped {wh_summary.records_skipped} replays", fg="green")

            # 4. Reconciliation
            click.echo(f"4. Audit reconciliation...")
            recon_engine = ReconciliationEngine(conn)
            report = recon_engine.reconcile_batch(b_id)
            if report.is_reconciled:
                click.secho(f"   [RECONCILED] Pipeline run for batch '{b_id}' completed and verified!", fg="green")
            else:
                click.secho(f"   [UNRECONCILED] Discrepancies detected:", fg="red")
                for d in report.discrepancies:
                    click.echo(f"     - {d}")

    except Exception as ex:
        click.secho(f"[ERROR] Pipeline run failed: {ex}", fg="red")
        sys.exit(1)


@cli.command("batch-status")
@click.argument("batch_id")
@click.option("--test-db", is_flag=True, help="Check batch status in test database.")
def batch_status_cmd(batch_id: str, test_db: bool):
    """Inspect status and metrics for a specific batch run."""
    settings = get_settings()
    db_config = settings.test_db if test_db else settings.db

    try:
        with get_connection(db_config) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT batch_id, source_name, started_at, completed_at, status,
                           records_extracted, records_staged, records_valid, records_rejected,
                           records_inserted, records_skipped, reconciliation_status,
                           error_summary
                    FROM monitoring.etl_batch_runs
                    WHERE batch_id = %s;
                """, (batch_id,))
                row = cur.fetchone()

                if not row:
                    click.secho(f"Batch '{batch_id}' not found.", fg="yellow")
                    return

                click.echo(f"Batch ID:           {row[0]}")
                click.echo(f"Source:             {row[1]}")
                click.echo(f"Started:            {row[2]}")
                click.echo(f"Completed:          {row[3]}")
                status_color = "green" if row[4] == "SUCCEEDED" else "yellow" if row[4] == "SUCCEEDED_WITH_REJECTIONS" else "red"
                click.secho(f"Status:             {row[4]}", fg=status_color)
                click.echo(f"Records Extracted:  {row[5]}")
                click.echo(f"Records Staged:     {row[6]}")
                click.echo(f"Records Valid:      {row[7]}")
                click.echo(f"Records Rejected:   {row[8]}")
                click.echo(f"Records Inserted:   {row[9] or 0}")
                click.echo(f"Records Skipped:    {row[10] or 0}")
                if row[11]:
                    recon_color = "green" if row[11] == "RECONCILED" else "red"
                    click.secho(f"Reconciliation:     {row[11]}", fg=recon_color)
                if row[12]:
                    click.echo(f"Error Summary:      {row[12]}")

                # Query issue count from monitoring.data_quality_issues
                cur.execute("""
                    SELECT count(*), count(DISTINCT source_row_id)
                    FROM monitoring.data_quality_issues
                    WHERE batch_id = %s;
                """, (batch_id,))
                issue_stats = cur.fetchone()
                if issue_stats and issue_stats[0] > 0:
                    click.echo(f"Quality Issues:     {issue_stats[0]} issues across {issue_stats[1]} distinct rows")

    except Exception as ex:
        click.secho(f"[ERROR] Query failed: {ex}", fg="red")
        sys.exit(1)


if __name__ == "__main__":
    cli()
