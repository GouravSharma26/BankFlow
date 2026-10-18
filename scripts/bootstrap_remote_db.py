"""
BankFlow Remote Database Bootstrap and Demo Data Seeder.

Safely initializes a remote PostgreSQL database (such as Neon Serverless Postgres),
configures the dedicated read-only reporting role, loads a small deterministic synthetic
dataset with realistic defect cases, and audits warehouse reconciliation.

Usage:
    python scripts/bootstrap_remote_db.py [--reporting-password <PASSWORD>] [--seed 42]
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bankflow.config import DatabaseConfig, get_settings
from bankflow.db import get_connection
from bankflow.generator import DefectConfig, SyntheticDataGenerator
from bankflow.reconciliation.reconciler import ReconciliationEngine
from bankflow.reporting.schema import init_reporting_schema
from bankflow.staging.loader import StagingLoader
from bankflow.staging.schema import init_staging_schema
from bankflow.validation.schema import init_validation_schema
from bankflow.validation.validator import ValidationEngine
from bankflow.warehouse.loader import WarehouseLoader
from bankflow.warehouse.schema import init_warehouse_schema


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap remote database schemas, reporting role, and synthetic demo data."
    )
    parser.add_argument(
        "--reporting-password",
        default=os.getenv("BANKFLOW_REPORTING_DB_PASSWORD"),
        help="Password for the dedicated bankflow_reporting_user role. Defaults to $BANKFLOW_REPORTING_DB_PASSWORD.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible synthetic data generation. Default: 42.",
    )
    parser.add_argument(
        "--transactions",
        type=int,
        default=500,
        help="Number of synthetic transactions to generate. Default: 500.",
    )
    parser.add_argument(
        "--skip-data-load",
        action="store_true",
        help="Initialize schemas and reporting role only without seeding synthetic data.",
    )
    return parser.parse_args()


def bootstrap_database(reporting_password: str | None = None, seed: int = 42, transactions: int = 500, skip_data_load: bool = False) -> None:
    settings = get_settings()
    admin_cfg = settings.db

    print("=" * 70)
    print("BankFlow — Remote Database Bootstrap & Demo Data Seeder")
    print("=" * 70)
    print(f"Target Database Host:     {admin_cfg.host}:{admin_cfg.port}")
    print(f"Target Database Name:     {admin_cfg.name}")
    print(f"Admin / Bootstrap User:   {admin_cfg.user}")
    print(f"SSL Mode:                 {admin_cfg.sslmode or 'default'}")
    print("=" * 70)

    # 1. Connectivity test
    print("\n[1/6] Connecting to target database...")
    try:
        with get_connection(admin_cfg) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                row = cur.fetchone()
                version = row[0] if row else "unknown"
                print(f"  [OK] Connected successfully! Engine: {version.split(',')[0]}")
    except Exception as exc:
        print(f"  [ERROR] Database connection failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # 2. Schema initialization
    print("\n[2/6] Initializing schemas (staging, validation, warehouse, reporting)...")
    try:
        with get_connection(admin_cfg) as conn:
            init_staging_schema(conn)
            print("  [OK] Staging and ops monitoring tables initialized.")
            init_validation_schema(conn)
            print("  [OK] Data quality issues and quarantine tables initialized.")
            init_warehouse_schema(conn)
            print("  [OK] Dimensional warehouse (dimensions & facts) initialized.")
            init_reporting_schema(conn)
            print("  [OK] Analytical reporting views initialized.")
    except Exception as exc:
        print(f"  [ERROR] Schema initialization failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # 3. Dedicated reporting role setup
    print("\n[3/6] Configuring dedicated read-only reporting role ('bankflow_reporting_user')...")
    reporting_sql_file = Path(__file__).resolve().parent.parent / "sql" / "06_reporting_role.sql"
    if not reporting_sql_file.exists():
        print(f"  [ERROR] Reporting role SQL file not found at: {reporting_sql_file}", file=sys.stderr)
        sys.exit(1)

    try:
        with get_connection(admin_cfg) as conn:
            with conn.cursor() as cur:
                # Read and execute role privilege grant statements
                with open(reporting_sql_file, "r", encoding="utf-8") as f:
                    cur.execute(f.read())

                if reporting_password and reporting_password.strip():
                    cur.execute(
                        "ALTER ROLE bankflow_reporting_user WITH PASSWORD %s;",
                        (reporting_password.strip(),),
                    )
                    print("  [OK] Set password for 'bankflow_reporting_user'.")
                else:
                    print("  [WARN] No reporting password provided. Use ALTER ROLE bankflow_reporting_user WITH PASSWORD '...';")
            conn.commit()
            print("  [OK] Dedicated least-privilege reporting role configured with SELECT on reporting views.")
    except Exception as exc:
        print(f"  [ERROR] Failed to configure reporting role: {exc}", file=sys.stderr)
        sys.exit(1)

    if skip_data_load:
        print("\n[INFO] Skipping demo data load (--skip-data-load requested).")
        print("\n[COMPLETE] Remote database bootstrap complete!")
        return

    # 4. Generate deterministic synthetic demo dataset
    print(f"\n[4/6] Generating synthetic demo dataset (seed={seed}, transactions={transactions})...")
    defect_config = DefectConfig.standard_test_defects()
    generator = SyntheticDataGenerator(seed=seed, defect_config=defect_config)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        files = generator.export_all(
            output_dir=tmp_path,
            num_branches=3,
            num_customers=25,
            num_accounts=50,
            num_transactions=transactions,
            start_date="2026-03-01",
            end_date="2026-03-15",
        )
        print(f"  [OK] Exported {len(files)} CSV files with standard quality defects for realistic reporting.")

        # 5. Ingestion, Validation, Warehouse Load, Reconciliation
        print("\n[5/6] Executing batch ETL pipeline: Stage -> Validate -> Warehouse Load -> Reconcile...")
        try:
            with get_connection(admin_cfg) as conn:
                loader = StagingLoader(conn)
                stage_res = loader.ingest_dataset_directory(tmp_path)
                batch_id = stage_res["batch_id"]
                print(f"  - Staged Batch:     {batch_id} ({stage_res['records_staged']} staged rows)")

                validator = ValidationEngine(conn)
                val_summary = validator.validate_batch(batch_id)
                print(f"  - Validation:       {val_summary.batch_status} ({val_summary.records_valid} valid, {val_summary.records_rejected} quarantined)")

                wh_loader = WarehouseLoader(conn)
                wh_summary = wh_loader.load_batch(batch_id)
                print(f"  - Warehouse Facts:  {wh_summary.records_inserted} inserted, {wh_summary.records_skipped} skipped")

                reconciler = ReconciliationEngine(conn)
                recon_report = reconciler.reconcile_batch(batch_id)
                print(f"  - Reconciliation:   {recon_report.status.value}")
                if not recon_report.is_reconciled:
                    print(f"  [WARN] Discrepancies detected: {recon_report.discrepancies}")
                else:
                    print("  [OK] Complete end-to-end reconciliation confirmed across all layers!")
        except Exception as exc:
            print(f"  [ERROR] Pipeline execution failed: {exc}", file=sys.stderr)
            sys.exit(1)

    # 6. Verify Reporting Role Access
    print("\n[6/6] Verifying read-only reporting role permissions on reporting schema...")
    if reporting_password and reporting_password.strip():
        reporting_cfg = DatabaseConfig(
            host=admin_cfg.host,
            port=admin_cfg.port,
            name=admin_cfg.name,
            user="bankflow_reporting_user",
            password=reporting_password.strip(),
            sslmode=admin_cfg.sslmode,
        )
        try:
            with get_connection(reporting_cfg) as rep_conn:
                with rep_conn.cursor() as rep_cur:
                    rep_cur.execute("SELECT currency, gross_transaction_amount, total_transaction_count FROM reporting.v_overview_metrics;")
                    rows = rep_cur.fetchall()
                    print(f"  [OK] Read-only reporting verification query succeeded! Returned {len(rows)} currency rows:")
                    for r in rows:
                        print(f"       - Currency: {r[0]} | Gross Value: {r[1]} | Volume: {r[2]}")
        except Exception as exc:
            print(f"  [ERROR] Reporting role verification failed: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print("  [INFO] Skipping reporting role verification query (no password specified).")

    print("\n" + "=" * 70)
    print("BankFlow — Remote Database Bootstrap Succeeded!")
    print("=" * 70)
    print("Database is ready for read-only reporting API deployment.")
    print("Set these environment variables on your FastAPI deployment (e.g. Render):")
    print(f"  BANKFLOW_DB_HOST={admin_cfg.host}")
    print(f"  BANKFLOW_DB_PORT={admin_cfg.port}")
    print(f"  BANKFLOW_DB_NAME={admin_cfg.name}")
    print(f"  BANKFLOW_DB_SSLMODE={admin_cfg.sslmode or 'require'}")
    print("  BANKFLOW_REPORTING_DB_USER=bankflow_reporting_user")
    print("  BANKFLOW_REPORTING_DB_PASSWORD=<CONFIGURED_PASSWORD>")
    print("=" * 70)


if __name__ == "__main__":
    args = parse_args()
    bootstrap_database(
        reporting_password=args.reporting_password,
        seed=args.seed,
        transactions=args.transactions,
        skip_data_load=args.skip_data_load,
    )
