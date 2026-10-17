# BankFlow — Portfolio Demonstration & Interview Walk-Through

> **Audience:** Data engineering reviewers, hiring managers, and technical interviewers.<br>
> **Project Target:** A reproducible, tested, production-pattern batch ETL and analytical warehouse using **synthetic banking data only**.<br>
> **Educational Disclaimer:** BankFlow is an educational simulation. It does not connect to live banking networks, process real customer records, or execute financial transactions.

---

## 1. Quick Technical Summary

BankFlow demonstrates end-to-end data engineering practices across the entire batch lifecycle:
- **Python-based Ingestion & Staging:** Structured CSV extraction with header contracts, explicit batch registration (`monitoring.etl_batch_runs`), and row-level source lineage (`staging.stg_*`).
- **Contract Validation & Quarantine Engine:** Deterministic rule evaluation rejecting bad rows with stable codes (`monitoring.data_quality_issues`) while preserving complete raw payloads in `quarantine.quarantined_records`.
- **Dimensional Star Schema Warehouse:** Conformed dimensions (`dim_date`, `dim_transaction_type`, `dim_branch`, `dim_customer`, `dim_account`) and transaction event facts (`warehouse.fact_transactions`).
- **Database-Enforced Idempotency & Replay Safety:** PostgreSQL unique constraints on `(source_system, transaction_id)` and conflict-safe inserts (`ON CONFLICT DO NOTHING`) with immutable payload verification. Rerunning a batch never creates duplicate facts.
- **Count & Monetary Reconciliation:** Traceable batch outcomes auditing extraction, staging, validation, insertion, and monetary amounts.
- **Conformed Analytical Reporting Schema:** Authoritative SQL views in `reporting.*` serving CLI analytics reports and a secure, read-only REST API (`src/bankflow/api`).
- **Strict Financial & Operational Hygiene:** PostgreSQL `NUMERIC(18,2)` / Python `Decimal` (zero floating-point math), grouped currencies only (no cross-currency summation), isolated test database guards, and CI automation.

---

## 2. Reproducible Clean-Clone Setup

Follow these steps from a clean clone in Windows PowerShell (or adapt to bash/zsh):

### Step 2.1 — Clone and Create Virtual Environment

```powershell
git clone https://github.com/GouravSharma26/BankFlow.git
cd BankFlow

# Create and activate Python 3.12 virtual environment
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install package with development and API dependencies
python -m pip install --upgrade pip
python -m pip install -e ".[dev,api]"
```

### Step 2.2 — Configure Environment and Launch PostgreSQL

```powershell
# Copy template configuration (do not overwrite if .env already exists)
Copy-Item .env.example .env

# Launch PostgreSQL 17 via Docker Compose
docker compose up -d --wait

# Verify database connectivity
python -m bankflow test-connection
python -m bankflow test-connection --test-db

# Initialize database schemas (staging, monitoring, quarantine, warehouse, reporting)
python -m bankflow init-db --test-db
```

*Note on Ports:* Docker Compose exposes PostgreSQL on loopback `127.0.0.1:5433` (or `5432` depending on `BANKFLOW_DB_PORT`). The initialization script automatically creates both `bankflow` and `bankflow_test`.

---

## 3. End-to-End Demonstration Guide

Execute each step below to inspect the system's runtime behavior:

### Step A: Clean Synthetic Batch Ingestion & Full Reconciliation

Generate a reproducible, clean synthetic dataset with 100 transactions and execute the full pipeline:

```powershell
# 1. Generate clean dataset (seed=42 ensures exact determinism)
python -m bankflow generate --output-dir data/demo_clean --seed 42 --branches 5 --customers 25 --accounts 40 --transactions 100

# 2. Run complete ETL pipeline (stage -> validate -> load -> reconcile)
python -m bankflow run -i data/demo_clean --batch-id demo-batch-001 --test-db
```

**Expected Console Output:**
```text
1. Ingesting staging records from data/demo_clean...
   [OK] Staged 170 records (batch: demo-batch-001)
2. Validating staged records for batch 'demo-batch-001'...
   [SUCCEEDED] Valid: 170 | Rejected: 0
3. Loading valid records into dimensional warehouse...
   [OK] Inserted 100 facts | Skipped 0 replays
4. Audit reconciliation...
   [RECONCILED] Pipeline run for batch 'demo-batch-001' completed and verified!
```

**Inspect Operational Batch Status:**
```powershell
python -m bankflow batch-status demo-batch-001 --test-db
```
```text
Batch ID:           demo-batch-001
Status:             SUCCEEDED
Records Extracted:  170
Records Staged:     170
Records Valid:      170
Records Rejected:   0
Records Inserted:   100
Records Skipped:    0
Reconciliation:     RECONCILED
```

**Run Explicit Reconciliation Audit:**
```powershell
python -m bankflow reconcile demo-batch-001 --test-db
```

---

### Step B: Database-Enforced Idempotency & Safe Replay

Re-run the exact same source dataset under a new batch ID to demonstrate that warehouse facts are never duplicated:

```powershell
python -m bankflow run -i data/demo_clean --batch-id demo-batch-001-replay --test-db
```

**Expected Console Output:**
```text
1. Ingesting staging records from data/demo_clean...
   [OK] Staged 170 records (batch: demo-batch-001-replay)
2. Validating staged records for batch 'demo-batch-001-replay'...
   [SUCCEEDED] Valid: 170 | Rejected: 0
3. Loading valid records into dimensional warehouse...
   [OK] Inserted 0 facts | Skipped 100 replays
4. Audit reconciliation...
   [RECONCILED] Pipeline run for batch 'demo-batch-001-replay' completed and verified!
```

**Reviewer Key Takeaway:** The database constraint `UNIQUE (source_system, transaction_id)` and atomic `ON CONFLICT DO NOTHING` safely identified all 100 replayed transactions. Exactly 0 facts were inserted, 100 replays were skipped, and the warehouse fact table remained free of duplicates.

---

### Step C: Data Quality Rule Enforcement & Quarantine Inventory

Generate a dataset with deliberately injected defect scenarios (missing IDs, invalid dates, unparseable amounts, unsupported statuses, currency mismatches, and conflicting replays):

```powershell
# 1. Generate defective dataset
python -m bankflow generate --output-dir data/demo_defects --seed 42 --transactions 100 --with-defects

# 2. Run ETL pipeline
python -m bankflow run -i data/demo_defects --batch-id demo-batch-defects-001 --test-db
```

**Expected Console Output:**
```text
1. Ingesting staging records from data/demo_defects...
   [OK] Staged 170 records (batch: demo-batch-defects-001)
2. Validating staged records for batch 'demo-batch-defects-001'...
   [SUCCEEDED_WITH_REJECTIONS] Valid: 156 | Rejected: 14
3. Loading valid records into dimensional warehouse...
   [OK] Inserted 0 facts | Skipped 86 replays
4. Audit reconciliation...
   [UNRECONCILED] Discrepancies detected:
     - Batch contains 1 conflicting replay payload(s) where transaction event identity was reused with mismatched data.
```

**Inspect Quarantined Inventory via CLI:**
```powershell
python -m bankflow report quality --test-db
python -m bankflow report quarantine --test-db
```
Reviewers can observe:
- Multi-issue recording: distinct rule violations (e.g. `DATE_PARSE_ERROR`, `TXN_ID_DUPLICATE`, `AMOUNT_PARSE_ERROR`) attached to specific source rows.
- Complete raw payloads retained in `staging.stg_*` without data loss.
- Non-zero exit code produced by the CLI when a batch finishes `UNRECONCILED`.

---

### Step D: Conformed SQL Reporting Views

Query the conformed analytical reporting layer directly via the CLI:

```powershell
# Daily activity summary by currency (USD)
python -m bankflow report daily --currency USD --test-db --limit 10

# Deposit vs withdrawal analysis
python -m bankflow report deposit-withdrawal --test-db

# Branch and channel activity breakdown
python -m bankflow report branch-channel --currency USD --test-db

# Pipeline execution health across all batches
python -m bankflow report batches --test-db
```

Reviewers can also run raw SQL queries directly using PostgreSQL client tools:
```powershell
psql -h localhost -p 5433 -U postgres -d bankflow_test -f sql/04_analytics_queries.sql
```

---

### Step E: Read-Only Reporting API & Health Endpoint

Start the FastAPI reporting server using the dedicated read-only role (`bankflow_reporting_user`):

```powershell
# In a separate terminal:
python -m bankflow serve --host 127.0.0.1 --port 8000 --test-db
```

**Verify Health Endpoint:**
```powershell
curl http://127.0.0.1:8000/api/v1/health
```
**Expected JSON Response:**
```json
{
  "status": "ok",
  "database": "healthy",
  "reporting_role": "bankflow_reporting_user",
  "read_only": true,
  "statement_timeout_ms": 5000,
  "database_name": "bankflow_test",
  "timestamp": "2026-10-17T12:50:00.000000Z"
}
```

**Query Authoritative Aggregated Metrics:**
```powershell
# Overview metrics grouped by currency
curl "http://127.0.0.1:8000/api/v1/overview?currency=USD"

# Daily breakdown
curl "http://127.0.0.1:8000/api/v1/daily?currency=USD&limit=5"
```

**Interactive OpenAPI Documentation:** Open `http://127.0.0.1:8000/docs` in your browser.

> [!NOTE]
> **Hosted Dashboard Boundary:** The hosted console at [`https://bankflow-analytics-console.lovable.app/`](https://bankflow-analytics-console.lovable.app/) runs in synthetic **Demo Mode** by default. To connect a local frontend build to your running BankFlow API, set `VITE_BANKFLOW_API_BASE_URL=http://localhost:8000`.

---

### Step F: Full Test Suite Verification

Run the entire automated test suite with mandatory PostgreSQL integration tests enforced:

```powershell
$env:BANKFLOW_REQUIRE_INTEGRATION_TESTS = "1"
python -m pytest tests -v
```

**Expected Result:** **168 passed, 0 skipped, 0 failed in ~12 minutes**.

---

## 4. Technical Interview Explanation & Architecture Defense

When discussing BankFlow in technical interviews, focus on these real engineering trade-offs:

### 1. Why a dimensional star schema rather than flat tables or raw 3NF?
- **Separation of Concerns:** 3NF is optimized for OLTP write-integrity, not analytical query efficiency. Staging preserves raw input in 3NF-like structures, while the warehouse star schema simplifies analytical queries, reduces JOIN complexity for analysts, and enables fast aggregations along conformed dimensions (date, branch, customer, account, transaction type).

### 2. How is idempotency enforced, and why is in-memory deduplication insufficient?
- In-memory sets only catch duplicates within the same process execution. They fail completely across worker restarts, parallel batch runs, and scheduled replays.
- BankFlow enforces idempotency at the database engine level via a composite unique constraint: `CONSTRAINT uq_fact_transactions_source_event UNIQUE (source_system, transaction_id)`.
- The loader uses `INSERT INTO warehouse.fact_transactions ... ON CONFLICT (source_system, transaction_id) DO NOTHING RETURNING transaction_id`.
- Furthermore, conflicting replay payloads (same event ID but changed amount/account/date) are explicitly detected by joining replayed records against existing facts, rejecting the modification and alerting the reconciler.

### 3. How do you distinguish a row rejection from a batch failure?
- **Row Rejection:** Row-level data contract violations (malformed dates, unparseable amounts, missing references) do not abort the entire batch. Valid rows are loaded, invalid rows are quarantined, and the batch enters state `SUCCEEDED_WITH_REJECTIONS`.
- **Batch Failure:** Fatal file-structure issues (missing headers, non-UTF-8 encoding, 0-byte files), database connection loss, or unhandled exceptions cause the transaction to roll back atomically, leaving the batch in `FAILED` state without partial or corrupted warehouse data.

### 4. Why avoid floating-point math for monetary amounts?
- IEEE 754 floating-point numbers cannot precisely represent base-10 decimal fractions (e.g. `0.1 + 0.2 != 0.3`). In financial systems, accumulated rounding errors cause reconciliation discrepancies.
- BankFlow parses amounts strictly as Python `Decimal` and stores them in PostgreSQL as `NUMERIC(18, 2)`.

### 5. Why group currencies rather than converting them on the fly?
- Speculative FX conversions introduce exchange-rate timing inaccuracies. Converting currencies without an auditable, timestamped FX rate table creates fabricated numbers. All analytical queries and API endpoints group strictly by currency.

### 6. What defense-in-depth security measures protect the reporting layer?
- Dedicated database role (`bankflow_reporting_user`) with permissions limited strictly to `SELECT` on `reporting.*`.
- Application-level session guard: `readonly=True`, `autocommit=True`, and 5-second `statement_timeout`.
- Paired credential validation: `ApiConfig.from_env` rejects mixed credentials and prevents password tampering.
- Zero secret storage in Git; isolated environment variables and non-echoing secret manager provisioning.

---

## 5. Known Limitations & Future Roadmap

- **Batch Processing Only:** BankFlow is designed as a batch ETL system. Streaming event ingestion (Kafka, Flink) is an architectural extension, not an MVP requirement.
- **Single-Node PostgreSQL:** The warehouse is hosted on a single PostgreSQL instance. Partitioning large fact tables by date range is documented as a future scale-out extension.
- **Cloud Infrastructure Deferred:** Cloud orchestration (Airflow, AWS ECS, GCP Cloud Run) and managed databases (AWS RDS, Cloud SQL) are deliberate post-MVP extensions to keep local execution simple, free, and completely reproducible.
