# BankFlow — Banking Transaction ETL & Analytics Warehouse

BankFlow is a Python and PostgreSQL portfolio project demonstrating an end-to-end batch ETL workflow on **synthetic banking data**. It ingests CSV files, preserves source lineage, validates data contracts, quarantines rejected records, loads a dimensional warehouse, detects duplicate/conflicting replays, and reconciles batch outcomes.

> **Scope:** BankFlow is an educational data engineering portfolio project using synthetic data only. It does not connect to real banks, process real customer records, or move real money. The implemented system includes batch ETL staging, contract validation, quarantine, a dimensional warehouse, idempotent replay protection, count/monetary reconciliation, SQL analytics, a read-only reporting API, and CI automation.

> [!TIP]
> **Reviewers & Interviewers:** See [`docs/demo_walkthrough.md`](docs/demo_walkthrough.md) for a step-by-step reproducible demonstration guide and interview talking points covering architecture, idempotency, data quality, and failure handling.

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
| API Layer | FastAPI, Uvicorn (optional extra `[api]`) |
| Database | PostgreSQL 17 |
| Data access | psycopg2 |
| Configuration | python-dotenv and environment variables |
| Local database | Docker Compose |
| Automated testing | pytest and PostgreSQL integration tests |
| Analytics | SQL over a dimensional warehouse |
| Dashboard Frontend | React 19, Vite, TypeScript, Tailwind CSS, Recharts (in `frontend/`) |

## Quickstart — Windows PowerShell

Prerequisites: Python 3.12, Docker Desktop with Compose, and Git.

### 1. Install the project

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,api]"
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
| `report REPORT_NAME` | Query conformed reporting views (`daily`, `deposit-withdrawal`, `branch-channel`, `type-mix`, `quality`, `batches`, `quarantine`, `transactions`) |
| `serve` | Start read-only FastAPI reporting server for dashboard console |
| `init-db` | Initialize staging, monitoring, quarantine, warehouse, and reporting schemas |
| `test-connection` | Verify database connectivity without logging credentials |

Use `--test-db` on commands that support it to target the dedicated test database instead of the primary local database.

## Tests

Start PostgreSQL first and ensure `bankflow_test` exists. Then run:

```powershell
python -m pytest tests -v
```

The integration tests must use the dedicated test database. Destructive test setup is guarded against non-test database names. CI is configured to require integration tests, so a missing test database should fail the workflow instead of silently skipping integration coverage.

## Analytics SQL & Reporting Views

BankFlow provides a conformed reporting layer in the dedicated `reporting` PostgreSQL schema (`sql/05_reporting_views.sql`) along with canonical executable SQL queries (`sql/04_analytics_queries.sql`).

You can inspect analytical reports using the CLI:

```powershell
python -m bankflow report daily --limit 10
python -m bankflow report deposit-withdrawal
python -m bankflow report branch-channel
python -m bankflow report type-mix
python -m bankflow report quality
python -m bankflow report batches
python -m bankflow report quarantine
python -m bankflow report transactions --limit 5
```

To run the raw SQL reporting queries from the repository root with a local `psql` client:

```powershell
psql "postgresql://postgres:postgres@localhost:5432/bankflow" -v ON_ERROR_STOP=1 -f sql/04_analytics_queries.sql
```

**Reporting Rules & Guardrails:**
- All reports group strictly by currency. Do not add different currencies together without an explicit FX-conversion policy.
- All transaction values represent gross positive event amounts; do not interpret gross event sums as net cash flow or account balances.
- Completed metrics filter strictly on `COMPLETED` transaction status. Reversals are tracked as discrete transaction events rather than destructive modifications.

## Dashboard Console & Analytics UI

BankFlow includes a dedicated, source-controlled frontend application in `frontend/` built with React 19, Vite, TypeScript, Tailwind CSS, Recharts, and Lucide React. It provides an interactive operational and analytical console called **BankFlow Analytics**.

### 1. Start the Reporting API Backend

```powershell
# In repository root with virtual environment activated:
python -m bankflow serve --host 127.0.0.1 --port 8000
```

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

### 2. Start the Frontend Dashboard

```powershell
# In a second terminal:
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

### 3. Operating Modes

- **Connected Mode (Default):** Fetches real-time aggregations from the local FastAPI backend and PostgreSQL warehouse. If the backend is unavailable or uninitialized, displays an honest connection error with retry actions (no silent mock fallback).
- **Demo Mode:** When `VITE_DEMO_MODE=true` is set in `frontend/.env` or toggled via the UI, renders deterministic synthetic preview fixtures and displays an unambiguous, persistent `DEMO DATA` banner so synthetic fixtures cannot be confused with live database state.
- **Historical Note:** The repository previously referenced an external hosted Lovable prototype. The in-repo `frontend/` application is now the primary, fully testable, source-controlled console.

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
Reporting Views (PostgreSQL `reporting` schema)
       |
       +---> Python CLI (`bankflow report`)
       |
       +---> Read-Only FastAPI (`bankflow serve`)
                   |
                   v
             BankFlow Analytics Console (`frontend/` React + Vite)
             [Optional external prototype: Lovable App]
```

Further details: [public deployment guide](docs/deployment.md) · [portfolio demo walk-through](docs/demo_walkthrough.md) · [architecture](docs/architecture.md) · [dashboard API contract](docs/dashboard_api_contract.md) · [data contract](docs/data_contract.md) · [data dictionary](docs/data_dictionary.md) · [quality rules](docs/data_quality_rules.md) · [metric definitions](docs/metric_definitions.md) · [testing strategy](docs/testing_strategy.md) · [developer setup](HUMAN_SETUP.md) · [development checklist](DEVELOPMENT_CHECKLIST.md).

## Public portfolio deployment

BankFlow is fully prepared for public portfolio deployment using zero-cost cloud tiers:

1. **Managed Database (Neon Serverless Postgres):** Provides PostgreSQL with SSL (`sslmode=require`). Initialize schemas, create the least-privilege `bankflow_reporting_user`, and load synthetic demo data using:
   ```bash
   python scripts/bootstrap_remote_db.py --seed 42 --transactions 500
   ```
2. **Read-Only Reporting API (Render / Docker):** Deploy the backend using the 1-click Render Blueprint ([`render.yaml`](render.yaml)), the containerized [`Dockerfile`](Dockerfile), or [`Procfile`](Procfile) with `bankflow serve --host 0.0.0.0`.
3. **Analytics Dashboard (Vercel / Netlify):** Deploy [`frontend/`](frontend/) with `VITE_BANKFLOW_API_BASE_URL` pointing to the public API. Routing is managed by [`frontend/vercel.json`](frontend/vercel.json) or [`netlify.toml`](netlify.toml).
4. **Automated Smoke Testing:** Validate the live deployment end-to-end without printing secrets:
   ```bash
   python scripts/smoke_test_deployment.py --api-url https://your-api.onrender.com --frontend-url https://your-dashboard.vercel.app
   ```

Complete step-by-step instructions, environment variable matrix, cold-start handling, and troubleshooting: [`docs/deployment.md`](docs/deployment.md).

## Limitations and safety

Use synthetic datasets only. Never commit `.env`, credentials, or real banking/customer data. Real banking integrations, live card transactions, and payment execution are out of scope.
