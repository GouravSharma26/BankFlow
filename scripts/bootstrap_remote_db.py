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
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from bankflow.config import DatabaseConfig, get_settings
from bankflow.db import get_connection
from bankflow.generator import DefectConfig, SyntheticDataGenerator
from bankflow.analytics.schema import init_reporting_schema
from bankflow.staging.loader import StagingLoader
from bankflow.staging.schema import init_staging_schema
from bankflow.validation.schema import init_validation_schema
from bankflow.validation.validator import ValidationEngine
from bankflow.warehouse.loader import WarehouseLoader
from bankflow.warehouse.reconciliation import ReconciliationEngine
from bankflow.warehouse.schema import init_warehouse_schema


class BootstrapPreflightError(ValueError):
    """Raised when remote database bootstrap preflight validation fails."""


def validate_bootstrap_target(
    admin_cfg: DatabaseConfig,
    confirm_target: Optional[str] = None,
    allow_local: bool = False,
    require_ssl: bool = True,
) -> None:
    """
    Validates that the target database configuration is safe for remote bootstrap.

    Rules:
    1. Rejects local targets (localhost, 127.0.0.1, ::1, 0.0.0.0) unless allow_local=True.
    2. Rejects remote targets lacking TLS/SSL configuration unless require_ssl=False.
    3. Requires explicit confirmation of the target host (via confirm_target matching admin_cfg.host).
    4. Refuses targets with empty host or database name.
    """
    host_lower = (admin_cfg.host or "").strip().lower()
    is_local = host_lower in ("localhost", "127.0.0.1", "::1", "0.0.0.0", "")

    # 1. Reject accidental local targets
    if is_local and not allow_local:
        raise BootstrapPreflightError(
            f"Accidental local target rejected: Host '{admin_cfg.host}' is a local target. "
            "The remote bootstrap script is intended for remote databases (e.g. Neon, Render). "
            "Pass --allow-local if you intentionally wish to bootstrap a local database."
        )

    # 2. Require TLS for remote targets
    if not is_local and require_ssl:
        ssl_mode = (admin_cfg.sslmode or "").strip().lower()
        if ssl_mode not in ("require", "verify-ca", "verify-full"):
            raise BootstrapPreflightError(
                f"Insecure remote target rejected: Host '{admin_cfg.host}' lacks required TLS/SSL configuration. "
                f"Current sslmode is '{admin_cfg.sslmode or 'none'}'. Hosted PostgreSQL deployments require TLS. "
                "Set BANKFLOW_DB_SSLMODE=require or append ?sslmode=require to DATABASE_URL (or pass --no-ssl to override)."
            )

    # 3. Target confirmation requirement
    if not confirm_target or not confirm_target.strip():
        raise BootstrapPreflightError(
            f"Explicit target confirmation required: To confirm bootstrapping '{admin_cfg.host}' ('{admin_cfg.name}'), "
            f"you must pass --confirm-target {admin_cfg.host}."
        )

    expected_host = (admin_cfg.host or "").strip().lower()
    expected_db = (admin_cfg.name or "").strip().lower()
    provided_target = confirm_target.strip().lower()
    valid_targets = {
        expected_host,
        f"{expected_host}/{expected_db}",
        f"{expected_host}:{admin_cfg.port}",
        f"{expected_host}:{admin_cfg.port}/{expected_db}",
    }
    if provided_target not in valid_targets:
        raise BootstrapPreflightError(
            f"Target confirmation mismatch: Provided '--confirm-target {confirm_target}' does not match "
            f"resolved target host '{admin_cfg.host}' (database: '{admin_cfg.name}')."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap remote database schemas, reporting role, and synthetic demo data."
    )
    parser.add_argument(
        "--confirm-target",
        dest="confirm_target",
        help="Explicitly confirm the resolved database hostname before connecting (e.g. --confirm-target ep-cool-fog.neon.tech).",
    )
    parser.add_argument(
        "--allow-local",
        action="store_true",
        help="Allow bootstrap to run against local database targets (e.g. localhost, 127.0.0.1).",
    )
    parser.add_argument(
        "--no-ssl",
        action="store_true",
        help="Disable mandatory TLS/SSL requirement for remote databases (not recommended for production).",
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


def bootstrap_database(
    reporting_password: str | None = None,
    seed: int = 42,
    transactions: int = 500,
    skip_data_load: bool = False,
    confirm_target: Optional[str] = None,
    allow_local: bool = False,
    no_ssl: bool = False,
) -> None:
    settings = get_settings()
    admin_cfg = settings.db

    # PREFLIGHT: Validate target safety and confirmation BEFORE connecting or executing any DDL
    validate_bootstrap_target(
        admin_cfg=admin_cfg,
        confirm_target=confirm_target,
        allow_local=allow_local,
        require_ssl=not no_ssl,
    )

    print("=" * 70)
    print("BankFlow — Remote Database Bootstrap & Demo Data Seeder")
    print("=" * 70)
    print(f"Target Database Host:     {admin_cfg.host}:{admin_cfg.port}")
    print(f"Target Database Name:     {admin_cfg.name}")
    print(f"Admin / Bootstrap User:   {admin_cfg.user}")
    print(f"SSL Mode:                 {admin_cfg.sslmode or 'none'}")
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
                    # Preserve password byte-for-byte; do not call .strip() on actual password
                    cur.execute(
                        "ALTER ROLE bankflow_reporting_user WITH PASSWORD %s;",
                        (reporting_password,),
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
            password=reporting_password,
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
        confirm_target=args.confirm_target,
        allow_local=args.allow_local,
        no_ssl=args.no_ssl,
    )
