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
    """Initialize PostgreSQL staging and monitoring schemas and tables."""
    settings = get_settings()
    db_config = settings.test_db if test_db else settings.db
    target_type = "test" if test_db else "primary"

    click.echo(f"Connecting to {target_type} database '{db_config.name}' on {db_config.host}:{db_config.port}...")
    try:
        with get_connection(db_config) as conn:
            init_staging_schema(conn)
        click.secho(f"[OK] Successfully initialized staging and monitoring schemas in '{db_config.name}'.", fg="green")
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
@click.option("--test-db", is_flag=True, help="Ingest into the test database instead of primary.")
def stage_cmd(input_dir: Path, batch_id: Optional[str], test_db: bool):
    """Ingest CSV files from a dataset directory into PostgreSQL staging tables."""
    settings = get_settings()
    db_config = settings.test_db if test_db else settings.db

    try:
        with get_connection(db_config) as conn:
            loader = StagingLoader(conn)
            click.echo(f"Starting staging ingestion from {input_dir}...")
            result = loader.ingest_dataset_directory(input_dir, batch_id=batch_id)

            if result["status"] == "SUCCEEDED":
                click.secho(f"[OK] Batch '{result['batch_id']}' succeeded!", fg="green")
                click.echo(f"  Extracted records: {result['records_extracted']}")
                click.echo(f"  Staged records:    {result['records_staged']}")
                for entity, count in result.get("entity_counts", {}).items():
                    click.echo(f"    - {entity}: {count}")
            else:
                click.secho(f"[ERROR] Batch '{result['batch_id']}' failed: [{result.get('error_code')}] {result.get('error_message')}", fg="red")
                sys.exit(1)

    except Exception as ex:
        click.secho(f"[ERROR] Staging ingestion failed: {ex}", fg="red")
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
                           records_extracted, records_staged, error_summary
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
                status_color = "green" if row[4] == "SUCCEEDED" else "red"
                click.secho(f"Status:             {row[4]}", fg=status_color)
                click.echo(f"Records Extracted:  {row[5]}")
                click.echo(f"Records Staged:     {row[6]}")
                if row[7]:
                    click.echo(f"Error Summary:      {row[7]}")
    except Exception as ex:
        click.secho(f"[ERROR] Query failed: {ex}", fg="red")
        sys.exit(1)


if __name__ == "__main__":
    cli()
