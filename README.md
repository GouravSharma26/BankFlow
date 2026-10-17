# BankFlow — Banking Transaction ETL & Analytics Warehouse

BankFlow is a Python and PostgreSQL portfolio project demonstrating an end-to-end batch ETL workflow on **synthetic banking data**. It ingests CSV files, preserves source lineage, validates data contracts, quarantines rejected records, loads a dimensional warehouse, detects duplicate/conflicting replays, and reconciles batch outcomes.

> **Scope:** BankFlow is a CLI-based data engineering project, not a banking product or hosted web dashboard. It does not connect to real banks, move money, or use real customer data. The implemented core includes ETL staging, validation/quarantine, dimensional loading, replay protection, and reconciliation. Cloud scheduling and a BI dashboard are optional follow-up work.

## Highlights

- **Repeatable batch ingestion:** CSV header checks, raw staging, batch IDs, row-level lineage, and seeded synthetic-data generation.
- **Data quality:** contract validation, rule-coded quality issues, rejected-record quarantine, and strict date/financial amount checks.
- **Dimensional warehouse:** PostgreSQL star schema with date, transaction-type, branch, customer, and account dimensions plus a transaction fact table.
- **Replay safety:** idempotent loads distinguish identical source-event replays from conflicting payloads; unique constraints and conflict-safe inserts support concurrent loading.
- **Reconciliation:** count/value checks across staged, accepted, rejected, and warehouse records; CLI returns a failure exit code when reconciliation fails.
- **Operational safety:** environment-based configuration, a dedicated test database, destructive-test guardrails, Docker Compose PostgreSQL, and automated tests.
- **Analytics SQL:** reusable reports for monthly transaction volumes, transaction-type/channel mix, branch activity, data-quality issues, batch health, and quarantine volume.

## Technology stack

| Area | Technology |
|---|---|
| Language / CLI | Python 3.12+, Click |
| Database | PostgreSQL 17 |
| Data access | psycopg2 |
| Configuration | python-dotenv and environment variables |
| Local database | Docker Compose |
| Automated testing | pytest and PostgreSQL integration tests |
| Analytics | SQL over a dimensional warehouse |

## Quickstart — Windows PowerShell

Prerequisites: Python 3.12, Docker Desktop with Compose, and Git.

### 1. Install the project

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 2. Configure and start PostgreSQL

```powershell
Copy-Item .env.example .env
docker compose up -d --wait
python -m bankflow test-connection
python -m bankflow init-db
```

If you already have a working `.env`, do not overwrite it. If host port 5432 is occupied, set `BANKFLOW_DB_PORT=5433` in `.env` before starting Compose. The Compose initialization script creates the separate `bankflow_test` database when a new database volume is initialized.

### 3. Run the clean end-to-end pipeline

```powershell
python -m bankflow generate --output-dir data/samples --seed 42 --branches 5 --customers 25 --accounts 40 --transactions 100
python -m bankflow run --input-dir data/samples --batch-id demo-clean-001
python -m bankflow batch-status demo-clean-001
```

The `run` command executes staging → validation → warehouse loading → reconciliation. A failed pipeline or `UNRECONCILED` result produces a non-zero exit code.

### 4. Try data-quality scenarios (optional)

```powershell
python -m bankflow generate --output-dir data/defective-sample --seed 42 --transactions 100 --with-defects
python -m bankflow run --input-dir data/defective-sample --batch-id demo-defects-001
python -m bankflow batch-status demo-defects-001
```

The defect generator exercises validation and quarantine rules. Inspect batch counts and quality issues rather than expecting every generated row to load.

## CLI reference

Run `python -m bankflow --help` for the installed command list.

| Command | Purpose |
|---|---|
| `generate` | Generate reproducible synthetic CSVs, optionally with defects |
| `stage` | Ingest a CSV dataset directory into staging |
| `validate BATCH_ID` | Validate staged records and quarantine rejected rows |
| `load BATCH_ID` | Load conformed dimensions and accepted transaction facts |
| `reconcile BATCH_ID` | Audit counts and monetary totals |
| `run` | Run staging, validation, loading, and reconciliation in one command |
| `batch-status BATCH_ID` | Inspect batch metrics and data-quality issue counts |
| `init-db` | Initialize staging, monitoring, quarantine, and warehouse schemas |
| `test-connection` | Verify database connectivity without logging credentials |

Use `--test-db` on commands that support it to target the dedicated test database instead of the primary local database.

## Tests

Start PostgreSQL first and ensure `bankflow_test` exists. Then run:

```powershell
python -m pytest tests -v
```

The integration tests must use the dedicated test database. Destructive test setup is guarded against non-test database names. CI is configured to require integration tests, so a missing test database should fail the workflow instead of silently skipping integration coverage.

## Analytics SQL

After initializing the schemas and loading at least one batch, run the reporting pack from the repository root with a local `psql` client. Adjust the connection string for your `.env`:

```powershell
psql "postgresql://postgres:postgres@localhost:5432/bankflow" -v ON_ERROR_STOP=1 -f sql/04_analytics_queries.sql
```

The queries report gross amounts grouped by currency. Do not add different currencies together without an explicit FX-conversion policy, and do not interpret gross totals as signed net cash flow.

## Architecture

```text
Synthetic CSV files
       |
       v
Staging + batch and row lineage
       |
       v
Validation engine ------> Data-quality issues + quarantine
       |
       v
Conformed dimensions + transaction facts (PostgreSQL star schema)
       |
       v
Count/value reconciliation + reporting SQL
```

Further details: [architecture](docs/architecture.md) · [data contract](docs/data_contract.md) · [data dictionary](docs/data_dictionary.md) · [quality rules](docs/data_quality_rules.md) · [metric definitions](docs/metric_definitions.md) · [testing strategy](docs/testing_strategy.md) · [developer setup](HUMAN_SETUP.md) · [development checklist](DEVELOPMENT_CHECKLIST.md).

## Deployment notes and limitations

The repeatable local deployment uses Docker Compose for PostgreSQL and the installed Python CLI. A scheduled/cloud deployment can run the CLI as a batch job with database credentials supplied through environment variables or `DATABASE_URL`; keep secrets out of source control. This repository does **not** currently provide a hosted HTTP endpoint or BI dashboard. Add cloud scheduling, a managed database, monitoring, and a dashboard as separate steps rather than describing them as already deployed.

Use synthetic datasets only. Never commit `.env`, credentials, or real banking/customer data.
