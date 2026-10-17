# BankFlow — Dashboard & Reporting API Contract

> **Status:** Implemented & Verified (Phase 5). This document serves as the authoritative interface specification between the BankFlow PostgreSQL dimensional warehouse reporting layer and the web frontend console.

## 1. Overview & Frontend Architecture

BankFlow provides a dedicated, read-only analytics reporting API built with **FastAPI** and **Uvicorn**. The API serves metrics directly from the conformed PostgreSQL `reporting` schema views (`sql/05_reporting_views.sql`) to web dashboards and client applications.

The primary frontend interface is the **BankFlow Analytics Console**:
- **Hosted Prototype:** [`https://bankflow-analytics-console.lovable.app/`](https://bankflow-analytics-console.lovable.app/)
- **Frontend Stack:** React, Tailwind CSS, Recharts, Lucide Icons
- **Operating Modes:**
  1. **Demo Mode (Default / Hosted):** When no API backend is configured (`VITE_BANKFLOW_API_BASE_URL` is unset), the console runs entirely in the browser using deterministic, synthetic sample datasets.
  2. **Warehouse-Connected Mode:** When `VITE_BANKFLOW_API_BASE_URL` is set (e.g. `http://localhost:8000` or a deployed HTTPS URL), the console fetches live aggregated metrics from the BankFlow PostgreSQL warehouse.

> [!IMPORTANT]
> **Hosted Deployment Notice:** The public Lovable console deployment at `https://bankflow-analytics-console.lovable.app/` currently operates in **Demo Mode**. It is not connected to a live database because no public database or backend server has been deployed to the internet. To view live warehouse metrics, run the API locally and point a local frontend build to it.

---

## 2. Security & Defense-in-Depth Controls

The reporting API is designed with defense-in-depth principles:

1. **Dedicated Database Role (`sql/06_reporting_role.sql`):**
   - Role: `bankflow_reporting_user`
   - Granted `USAGE` and `SELECT` exclusively on the `reporting` schema.
   - All access to `staging`, `monitoring`, `quarantine`, and `warehouse` base tables is explicitly revoked.
   - Default role attributes: `default_transaction_read_only = on`, `statement_timeout = '5000ms'`.
2. **Application-Level Read-Only Enforcement:**
   - Every database session executes `conn.set_session(readonly=True, autocommit=True)`.
   - Query execution timeout is enforced via `SET statement_timeout = '5000ms'`.
   - Any attempt to execute `INSERT`, `UPDATE`, `DELETE`, or DDL statements is rejected by PostgreSQL with `ReadOnlySqlTransaction`.
3. **No Arbitrary SQL Endpoints:**
   - The API exposes only predefined, versioned GET endpoints.
   - All database queries use parameterized SQL (`%s` placeholders).
   - Dynamic sorting and ordering use strict in-memory whitelists.
4. **CORS Restrictions:**
   - Permitted origins are restricted via `BANKFLOW_CORS_ORIGINS` (defaults to local Vite/React development ports and `https://bankflow-analytics-console.lovable.app`). Wildcards (`*`) with credentials are prohibited.
5. **Zero Credential Exposure:**
   - Health check probes and error handlers sanitize database errors; passwords, database hostnames, internal paths, and query text are never exposed to clients.
   - No shared API secrets or tokens are embedded in frontend client bundles.

---

## 3. Core Metric Semantics

All API endpoints adhere strictly to the BankFlow metric contract:
- **Strict Currency Isolation:** All monetary metrics are grouped strictly by currency. Cross-currency summation and speculative FX conversion are strictly prohibited.
- **Gross Event Amounts:** Transaction amounts represent discrete, positive event values in the dimensional warehouse. They do not represent net cash flow, profit, or running account balances.
- **UTC Date Standardization:** All dates and timestamps are anchored to UTC calendar dates (`YYYY-MM-DD`) derived from `warehouse.dim_date`.
- **Status Inclusion Rules:** Completed metrics filter strictly on `COMPLETED` transaction status. Reversals (`REVERSAL` transaction type or `REVERSED` status) are tracked as discrete adjustment events and never silently decremented from gross event totals.
- **Precision Formatting:** All monetary quantities are returned as exact 2-decimal strings (e.g. `"150.00"`) to avoid floating-point rounding errors in JavaScript clients.

---

## 4. API Endpoints Specification

Base path: `/api/v1`

### 4.1 System Endpoints

#### `GET /api/v1/health`
Check service health and database availability.

- **Success Response (200 OK):**
  ```json
  {
    "status": "healthy",
    "service": "bankflow-reporting-api",
    "version": "0.1.0",
    "database": "connected"
  }
  ```
- **Degraded Response (503 Service Unavailable):**
  ```json
  {
    "status": "degraded",
    "service": "bankflow-reporting-api",
    "version": "0.1.0",
    "database": "unavailable"
  }
  ```

---

### 4.2 Analytics Endpoints

#### `GET /api/v1/overview`
Executive KPI summary cards and portfolio context.

- **Query Parameters:**
  - `currency` *(optional, string)*: Filter by 3-letter ISO code (e.g. `USD`).
- **Response (200 OK):**
  ```json
  {
    "currencies": ["EUR", "USD"],
    "earliest_date": "2026-03-01",
    "latest_date": "2026-03-31",
    "metrics_by_currency": [
      {
        "currency": "USD",
        "total_transactions": 100,
        "completed_transactions": 85,
        "gross_transaction_amount": "25450.00",
        "completed_gross_amount": "21800.00",
        "acceptance_rate_pct": "85.00",
        "active_accounts": 40,
        "active_customers": 25
      }
    ],
    "total_batches": 3,
    "latest_batch_status": "SUCCEEDED",
    "total_quality_issues": 12,
    "total_quarantined_records": 8
  }
  ```

---

#### `GET /api/v1/daily`
Daily transaction volume trends and gross event value.

- **Query Parameters:**
  - `currency` *(optional, string)*: Filter by 3-letter ISO code.
  - `start_date` *(optional, string)*: Start date (`YYYY-MM-DD`).
  - `end_date` *(optional, string)*: End date (`YYYY-MM-DD`).
  - `limit` *(optional, int, default: 30, min: 1, max: 365)*: Number of daily rows.
- **Response (200 OK):**
  ```json
  [
    {
      "date_key": 20260315,
      "reporting_date": "2026-03-15",
      "year_number": 2026,
      "month_number": 3,
      "month_name": "March",
      "day_name": "Sunday",
      "is_weekend": true,
      "currency": "USD",
      "total_transaction_count": 10,
      "completed_transaction_count": 8,
      "pending_transaction_count": 0,
      "failed_transaction_count": 1,
      "reversed_transaction_count": 1,
      "active_accounts": 8,
      "active_customers": 7,
      "gross_transaction_amount": "735.00",
      "completed_gross_amount": "650.00"
    }
  ]
  ```

---

#### `GET /api/v1/deposit-withdrawal`
Comparative deposit vs withdrawal volume and value share.

- **Query Parameters:**
  - `currency` *(optional, string)*: Filter by 3-letter ISO code.
  - `start_date` *(optional, string)*: Start date (`YYYY-MM-DD`).
  - `end_date` *(optional, string)*: End date (`YYYY-MM-DD`).
  - `limit` *(optional, int, default: 30, min: 1, max: 365)*.
- **Response (200 OK):**
  ```json
  [
    {
      "date_key": 20260315,
      "reporting_date": "2026-03-15",
      "currency": "USD",
      "deposit_count": 5,
      "deposit_gross_amount": "500.00",
      "completed_deposit_count": 5,
      "completed_deposit_gross_amount": "500.00",
      "withdrawal_count": 3,
      "withdrawal_gross_amount": "150.00",
      "completed_withdrawal_count": 3,
      "completed_withdrawal_gross_amount": "150.00",
      "reversal_count": 1,
      "reversal_gross_amount": "10.00",
      "deposit_value_share_pct": "76.92",
      "withdrawal_value_share_pct": "23.08"
    }
  ]
  ```

---

#### `GET /api/v1/branch-channel`
Distribution of events and gross value by branch, region, and channel.

- **Query Parameters:**
  - `currency` *(optional, string)*: Filter by 3-letter ISO code.
  - `channel` *(optional, string)*: Whitelisted values: `BRANCH`, `ATM`, `ONLINE`, `MOBILE`.
  - `branch_id` *(optional, string)*: Branch identifier.
  - `region` *(optional, string)*: Regional identifier.
  - `limit` *(optional, int, default: 50, min: 1, max: 200)*.
- **Response (200 OK):**
  ```json
  [
    {
      "region": "NORTH",
      "branch_id": "BR-001",
      "branch_name": "Downtown Branch",
      "channel": "BRANCH",
      "currency": "USD",
      "total_transaction_count": 25,
      "completed_transaction_count": 22,
      "distinct_accounts": 18,
      "distinct_customers": 15,
      "gross_transaction_amount": "5420.00",
      "completed_gross_amount": "4950.00"
    }
  ]
  ```

---

#### `GET /api/v1/type-mix`
Portfolio mix across accounting families and transaction types.

- **Query Parameters:**
  - `currency` *(optional, string)*: Filter by 3-letter ISO code.
- **Response (200 OK):**
  ```json
  [
    {
      "transaction_type_code": "DEPOSIT",
      "transaction_type_name": "Deposit",
      "transaction_family": "CREDIT",
      "currency": "USD",
      "total_transaction_count": 50,
      "completed_transaction_count": 48,
      "failed_transaction_count": 1,
      "pending_transaction_count": 1,
      "reversed_transaction_count": 0,
      "gross_transaction_amount": "12500.00",
      "completed_gross_amount": "12000.00",
      "event_share_pct": "50.00",
      "value_share_pct": "68.03"
    }
  ]
  ```

---

### 4.3 Monitoring & Quality Endpoints

#### `GET /api/v1/quality`
Data quality defect inventory distinguishing issue records from affected source rows.

- **Query Parameters:**
  - `severity` *(optional, string)*: `ERROR`, `WARNING`, `INFO`.
  - `disposition` *(optional, string)*: `REJECTED`, `QUARANTINED`, `SKIPPED`, `LOGGED`.
  - `limit` *(optional, int, default: 50, min: 1, max: 200)*.
- **Response (200 OK):**
  ```json
  [
    {
      "rule_code": "RULE_AMOUNT_NON_POSITIVE",
      "severity": "ERROR",
      "disposition": "REJECTED",
      "issue_count": 4,
      "affected_source_rows": 4,
      "affected_batches": 1
    }
  ]
  ```

---

#### `GET /api/v1/batches`
ETL batch execution health, row accounting, and reconciliation status.

- **Query Parameters:**
  - `status` *(optional, string)*: Filter by batch lifecycle status (`SUCCEEDED`, `FAILED`, etc.).
  - `reconciliation_status` *(optional, string)*: `RECONCILED`, `UNRECONCILED`, `DISCREPANCY_DETECTED`.
  - `limit` *(optional, int, default: 20, min: 1, max: 100)*.
- **Response (200 OK):**
  ```json
  [
    {
      "batch_id": "batch-20260315-001",
      "source_name": "CORE_BANKING_DAILY",
      "started_at": "2026-03-15T12:00:00+00:00",
      "completed_at": "2026-03-15T12:00:03+00:00",
      "duration_seconds": 3.12,
      "status": "SUCCEEDED",
      "records_extracted": 100,
      "records_staged": 100,
      "records_valid": 95,
      "records_rejected": 5,
      "records_inserted": 95,
      "records_updated": 0,
      "records_skipped": 0,
      "rejection_rate_pct": "5.00",
      "reconciliation_status": "RECONCILED",
      "error_summary": null
    }
  ]
  ```

---

#### `GET /api/v1/quarantine`
Quarantine table inventory by batch and entity.

- **Query Parameters:**
  - `batch_id` *(optional, string)*: Filter by batch identifier.
  - `entity_type` *(optional, string)*: `BRANCH`, `CUSTOMER`, `ACCOUNT`, `TRANSACTION`.
  - `primary_rule_code` *(optional, string)*: Filter by primary rejection rule code.
  - `limit` *(optional, int, default: 50, min: 1, max: 200)*.
- **Response (200 OK):**
  ```json
  [
    {
      "batch_id": "batch-20260315-001",
      "entity_type": "TRANSACTION",
      "primary_rule_code": "RULE_TRANSACTION_DATE_FUTURE",
      "quarantined_rows": 5,
      "recorded_issue_count": 7,
      "first_quarantined_at": "2026-03-15T12:00:01+00:00",
      "last_quarantined_at": "2026-03-15T12:00:01+00:00"
    }
  ]
  ```

---

### 4.4 Transaction Search & Details

#### `GET /api/v1/transactions`
Paginated, sorted, and filtered transaction details for the console Transactions page.

- **Query Parameters:**
  - `page` *(optional, int, default: 1, min: 1)*: Page number.
  - `page_size` *(optional, int, default: 25, min: 1, max: 100)*: Rows per page.
  - `currency` *(optional, string)*: 3-letter ISO code.
  - `status` *(optional, string)*: `COMPLETED`, `PENDING`, `FAILED`, `REVERSED`.
  - `transaction_type` *(optional, string)*: `DEPOSIT`, `WITHDRAWAL`, `TRANSFER`, `PAYMENT`, `FEE`, `REVERSAL`.
  - `channel` *(optional, string)*: `BRANCH`, `ATM`, `ONLINE`, `MOBILE`.
  - `start_date` *(optional, string)*: Start date (`YYYY-MM-DD`).
  - `end_date` *(optional, string)*: End date (`YYYY-MM-DD`).
  - `sort_by` *(optional, string, default: `transaction_timestamp`)*: Whitelisted: `transaction_timestamp`, `amount`, `transaction_id`, `reporting_date`.
  - `sort_order` *(optional, string, default: `desc`)*: `asc` or `desc`.
- **Response (200 OK):**
  ```json
  {
    "items": [
      {
        "transaction_id": "TXN-100480",
        "source_system": "CORE",
        "account_id": "ACC-3369",
        "customer_id": "CUST-1042",
        "branch_id": "BR-001",
        "branch_name": "Downtown Branch",
        "region": "NORTH",
        "transaction_type": "PAYMENT",
        "type_name": "Payment",
        "transaction_family": "DEBIT",
        "amount": "962.17",
        "currency": "USD",
        "status": "COMPLETED",
        "channel": "MOBILE",
        "transaction_timestamp": "2026-03-15T10:14:22+00:00",
        "reporting_date": "2026-03-15",
        "batch_id": "batch-20260315-001",
        "loaded_at": "2026-03-15T12:00:02+00:00"
      }
    ],
    "total": 1,
    "page": 1,
    "page_size": 25,
    "total_pages": 1
  }
  ```

---

## 5. Local Setup & Verification Guide

### 5.1 Prerequisites & Installation
Install BankFlow with both development and API dependencies:

```powershell
python -m pip install -e ".[dev,api]"
```

### 5.2 Start PostgreSQL & Initialize Schemas
Ensure PostgreSQL 17 is running via Docker Compose:

```powershell
docker compose up -d --wait
python -m bankflow init-db
```

### 5.3 Ingest a Clean Batch
Generate and load synthetic test transactions:

```powershell
python -m bankflow generate --output-dir data/samples --seed 42 --transactions 100
python -m bankflow run --input-dir data/samples --batch-id demo-batch-001
```

### 5.4 Launch the Reporting API Server
Start the read-only FastAPI server:

```powershell
python -m bankflow serve --host 127.0.0.1 --port 8000 --reload
```

Interactive OpenAPI documentation is immediately accessible at:
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

### 5.5 Connecting the Frontend Locally
In your local clone of the Lovable frontend console:
1. Create or edit `.env.local`:
   ```bash
   VITE_BANKFLOW_API_BASE_URL=http://localhost:8000
   ```
2. Start the Vite dev server:
   ```bash
   npm run dev
   ```
3. Open `http://localhost:5173` in your browser. The console will connect to the local API server and display data loaded into your PostgreSQL warehouse.
