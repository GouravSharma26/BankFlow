# BankFlow — Production Portfolio Deployment Guide

> **Scope & Safety Notice:** BankFlow is an educational batch ETL, analytics warehouse, and reporting console built exclusively with **synthetic data**. It does not connect to live banking networks, process real funds, or store personal customer data. This guide provides instructions for deploying a public portfolio demonstration connecting the React dashboard, FastAPI reporting API, and a managed PostgreSQL database.

---

## 1. Deployment Architecture & Provider Selection

The public portfolio deployment connects three decoupled components over secure HTTPS/TLS:

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                      Client Web Browser                                  │
│   (Visitor opens https://bankflow-analytics.vercel.app)                 │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                 HTTPS GET (REST API)│ CORS: exact origin permitted
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              FastAPI Read-Only Reporting API                            │
│   (Hosted on Render Free Web Service: https://bankflow-api.onrender.com)│
│   - Binds to 0.0.0.0:$PORT                                              │
│   - Enforces read-only HTTP methods (GET, OPTIONS)                      │
│   - Connects using dedicated 'bankflow_reporting_user' role             │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                     PostgreSQL TLS  │ sslmode=require
                     Port 5432       │ default_transaction_read_only = on
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│              Managed PostgreSQL Database                                │
│   (Hosted on Neon Serverless Postgres / Supabase / Render)              │
│   - Staging, ops monitoring, quarantine, and warehouse schemas          │
│   - Relational analytical reporting views (reporting.v_*)               │
│   - Populated strictly with reproducible synthetic demo dataset         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Provider Evaluation & Trade-off Matrix

| Layer | Recommended Provider | Free Tier Specification | Cold-Start / Expiration Trade-offs | Alternative Providers |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend Dashboard** | **Vercel** or **Netlify** | Free Hobby / Starter. Unlimited static requests, 100GB bandwidth/mo, global edge CDN. | **Zero cold starts.** Instant edge asset delivery. Configured via [`frontend/vercel.json`](../frontend/vercel.json) or [`netlify.toml`](../netlify.toml). | Cloudflare Pages, GitHub Pages |
| **FastAPI Backend** | **Render Web Service** | Free instance (0.1 CPU, 512MB RAM, 750 free instance hours/month). Native Python 3.12 or Docker. | **Cold start:** Spins down after 15 minutes of inactivity. First incoming request takes **30–50 seconds** to wake up. UI handles this honestly with loading and retry indicators. | Koyeb (no sleep on nano), Fly.io (card required), Railway (trial credits) |
| **Managed PostgreSQL** | **Neon Serverless Postgres** | Free tier: 0.5 GB storage, autoscaling serverless compute, unlimited projects. | **Instant wake-up (~500ms).** Requires `sslmode=require`. **Does NOT expire** as long as active once/month. *(Note: Render free postgres deletes after 30 days; Supabase pauses after 7 days idle).* | Supabase (manual unpause after 7 days), Aiven |

---

## 2. Step 1: Database Provisioning & Schema Bootstrapping

### 2.1 Provision a Free Neon Database
1. Sign up at [neon.tech](https://neon.tech/) (free, no credit card required).
2. Create a project named `bankflow-portfolio` in your preferred region.
3. In the Neon Dashboard, copy the connection string (with pooled or direct connection):
   ```text
   postgresql://alex:AbCdEf123456@ep-cool-fog-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

### 2.2 Configure Local Environment Variables for Bootstrap
On your local developer workstation, set the administrative database connection variables pointing to the remote database:

```bash
# Linux / macOS / Git Bash
export BANKFLOW_DB_HOST="ep-cool-fog-123456.us-east-2.aws.neon.tech"
export BANKFLOW_DB_PORT="5432"
export BANKFLOW_DB_NAME="neondb"
export BANKFLOW_DB_USER="alex"
export BANKFLOW_DB_PASSWORD="your_neon_admin_password"
export BANKFLOW_DB_SSLMODE="require"

# Dedicated read-only reporting password to provision
export BANKFLOW_REPORTING_DB_PASSWORD="generate_a_secure_reporting_password_here"
```

```powershell
# Windows PowerShell
$env:BANKFLOW_DB_HOST="ep-cool-fog-123456.us-east-2.aws.neon.tech"
$env:BANKFLOW_DB_PORT="5432"
$env:BANKFLOW_DB_NAME="neondb"
$env:BANKFLOW_DB_USER="alex"
$env:BANKFLOW_DB_PASSWORD="your_neon_admin_password"
$env:BANKFLOW_DB_SSLMODE="require"

$env:BANKFLOW_REPORTING_DB_PASSWORD="generate_a_secure_reporting_password_here"
```

### 2.3 Run the Bootstrap and Demo Seeder Script
Execute the repository's bootstrap script to initialize all database schemas, create the least-privilege `bankflow_reporting_user`, generate a reproducible synthetic banking dataset (seed 42 with realistic validation defects), load the dimensional warehouse, and audit count and value reconciliation:

```bash
python scripts/bootstrap_remote_db.py --seed 42 --transactions 500
```

**What this command does:**
1. Tests administrative connection to the cloud database with SSL enabled.
2. Initializes `staging`, `monitoring`, `quarantine`, `warehouse`, and `reporting` schemas idempotently (`CREATE IF NOT EXISTS`).
3. Runs [`sql/06_reporting_role.sql`](../sql/06_reporting_role.sql) to create `bankflow_reporting_user`, revokes all privileges on application schemas, grants `SELECT` exclusively on `reporting.v_*` views, and enforces `default_transaction_read_only = on` and statement timeouts.
4. Generates 500 synthetic transactions across branches, accounts, and customers with standard test defect cases.
5. Ingests via `StagingLoader`, validates via `ValidationEngine`, loads the dimensional warehouse via `WarehouseLoader`, and verifies batch reconciliation via `ReconciliationEngine`.
6. Executes a read-only reporting verification query using `bankflow_reporting_user`.

---

## 3. Step 2: FastAPI Reporting Service Deployment

### Option A: Render Blueprint (Recommended 1-Click)
The repository contains [`render.yaml`](../render.yaml).

1. Log into [render.com](https://render.com/).
2. Click **New +** -> **Blueprint**.
3. Connect your GitHub repository `https://github.com/GouravSharma26/BankFlow`.
4. Render will parse [`render.yaml`](../render.yaml) and prompt for the un-synced secrets:
   - `BANKFLOW_DB_HOST`: your remote database hostname
   - `BANKFLOW_DB_NAME`: your database name (e.g., `neondb`)
   - `BANKFLOW_DB_USER`: `bankflow_reporting_user` (or admin user if using reporting role credentials)
   - `BANKFLOW_DB_PASSWORD`: password
   - `BANKFLOW_DB_SSLMODE`: `require`
   - `BANKFLOW_REPORTING_DB_USER`: `bankflow_reporting_user`
   - `BANKFLOW_REPORTING_DB_PASSWORD`: the password set during bootstrap
   - `BANKFLOW_CORS_ORIGINS`: comma-separated allowed frontend origins (e.g., `https://bankflow-analytics.vercel.app,http://localhost:5173`)
5. Click **Apply**. Render will install dependencies and start `bankflow serve --host 0.0.0.0`.
6. Note the public URL assigned to your API (e.g., `https://bankflow-api.onrender.com`).

### Option B: Render Web Service (Manual)
1. In Render, select **New +** -> **Web Service**.
2. Connect `https://github.com/GouravSharma26/BankFlow`.
3. Configure the service settings:
   - **Environment:** `Python 3`
   - **Branch:** `main`
   - **Build Command:** `pip install --upgrade pip && pip install -e ".[api]"`
   - **Start Command:** `bankflow serve --host 0.0.0.0`
   - **Health Check Path:** `/api/v1/health`
4. In **Environment Variables**, add the variables listed above.

### Option C: Container Deployment (Docker PaaS)
To deploy as a container on Koyeb, Fly.io, Railway, or Cloud Run, build and run using the repository's root [`Dockerfile`](../Dockerfile):
```bash
docker build -t bankflow-api .
docker run -p 8000:8000 \
  -e BANKFLOW_DB_HOST="ep-cool-fog-123456.us-east-2.aws.neon.tech" \
  -e BANKFLOW_DB_NAME="neondb" \
  -e BANKFLOW_DB_SSLMODE="require" \
  -e BANKFLOW_REPORTING_DB_USER="bankflow_reporting_user" \
  -e BANKFLOW_REPORTING_DB_PASSWORD="your_reporting_password" \
  -e BANKFLOW_CORS_ORIGINS="https://bankflow.vercel.app" \
  bankflow-api
```

---

## 4. Step 3: React Analytics Frontend Deployment

### Deploy on Vercel
1. Sign up or log into [vercel.com](https://vercel.com/).
2. Click **Add New...** -> **Project** -> Import `GouravSharma26/BankFlow`.
3. Configure project settings:
   - **Root Directory:** Edit and set to `frontend` (crucial: Vite app lives in `frontend/`).
   - **Framework Preset:** `Vite` (auto-detected).
   - **Build Command:** `npm run build` (`tsc -b && vite build`).
   - **Output Directory:** `dist`.
4. In **Environment Variables**, add:
   ```text
   VITE_BANKFLOW_API_BASE_URL = https://bankflow-api.onrender.com
   VITE_DEMO_MODE = false
   ```
5. Click **Deploy**. Vercel will build and publish your dashboard at e.g. `https://bankflow-analytics.vercel.app`.
6. Client-side routing is handled automatically by [`frontend/vercel.json`](../frontend/vercel.json).

### Deploy on Netlify
1. Log into [netlify.com](https://netlify.com/) -> **Add new site** -> **Import an existing project**.
2. Connect `GouravSharma26/BankFlow`.
3. Netlify will detect [`netlify.toml`](../netlify.toml):
   - **Base directory:** `frontend`
   - **Build command:** `npm run build`
   - **Publish directory:** `frontend/dist`
4. Under **Site configuration** -> **Environment variables**, add:
   ```text
   VITE_BANKFLOW_API_BASE_URL = https://bankflow-api.onrender.com
   VITE_DEMO_MODE = false
   ```
5. SPA redirects are handled by [`frontend/public/_redirects`](../frontend/public/_redirects) and [`netlify.toml`](../netlify.toml).

---

## 5. Step 4: Production Verification & Smoke Testing

After deploying the backend API and frontend console, run the automated smoke test script from your workstation:

```bash
python scripts/smoke_test_deployment.py \
  --api-url https://bankflow-api.onrender.com \
  --frontend-url https://bankflow-analytics.vercel.app
```

### Verified Checks (13 Automated Smoke Tests)
1. **API Root Info (`GET /`):** Verifies service metadata and version.
2. **Health & Database (`GET /api/v1/health`):** Verifies HTTP 200, status `healthy`, and database `connected`.
3. **Overview Metrics (`GET /api/v1/overview?currency=USD`):** Verifies gross amount, counts, and active currency lists.
4. **Daily Trends (`GET /api/v1/daily?currency=USD&limit=5`):** Verifies time-series volume trends.
5. **Deposit / Withdrawal Share (`GET /api/v1/deposit-withdrawal?currency=USD`):** Verifies value distribution.
6. **Branch & Channel Breakdown (`GET /api/v1/branch-channel?currency=USD&limit=5`):** Verifies dimension queries.
7. **Type Mix (`GET /api/v1/type-mix?currency=USD`):** Verifies transaction family aggregates.
8. **Data Quality Defect Inventory (`GET /api/v1/quality?limit=5`):** Verifies stable rule codes.
9. **Batch Execution History (`GET /api/v1/batches?limit=5`):** Verifies batch audit records and reconciliation status.
10. **Transactions Ledger (`GET /api/v1/transactions?page=1&page_size=5`):** Verifies paginated facts.
11. **CORS Preflight (`OPTIONS /api/v1/overview`):** Verifies that the deployed frontend origin is permitted.
12. **Read-Only Protection (`POST /api/v1/overview`):** Verifies that state-modifying requests are rejected with HTTP 405 Method Not Allowed.
13. **Frontend UI Delivery (`GET <frontend-url>`):** Verifies HTTP 200 and HTML index document receipt.

---

## 6. Troubleshooting & Operational Runbook

### Issue: "Unable to connect to BankFlow API" (Render Cold Start)
- **Symptom:** The frontend displays an error banner with a retry button upon the first page load after 15 minutes of inactivity.
- **Cause:** Render free-tier services sleep when idle. Spin-up takes ~30–50 seconds.
- **Remedy:** Wait 30 seconds and click **Retry Connection**. Once the API wakes up, queries respond in milliseconds.

### Issue: CORS Policy Error in Browser Console
- **Symptom:** Browser reports `Access to fetch at ... from origin ... has been blocked by CORS policy`.
- **Cause:** The deployed frontend origin (e.g., `https://bankflow.vercel.app`) is not listed in `BANKFLOW_CORS_ORIGINS`.
- **Remedy:** In Render dashboard -> Environment Variables, update `BANKFLOW_CORS_ORIGINS`:
  ```text
  BANKFLOW_CORS_ORIGINS=https://bankflow.vercel.app,http://localhost:5173
  ```
  Save and trigger a redeploy.

### Issue: PostgreSQL SSL Error ("no pg_hba.conf entry for host ... SSL off")
- **Symptom:** FastAPI service logs `OperationalError: connection failed: ... SSL off`.
- **Cause:** Remote database requires TLS, but SSL was disabled.
- **Remedy:** Ensure `BANKFLOW_DB_SSLMODE=require` is configured in the backend environment.

### Issue: Permission Denied on Writing Staging or Warehouse Tables
- **Symptom:** The reporting API fails if an unauthorized write is attempted.
- **Resolution:** This is intentional behavior. The reporting user (`bankflow_reporting_user`) is strictly read-only and restricted to `SELECT` on `reporting.v_*` views. Batch ETL writes must be executed using administrative bootstrap credentials.

---

## 7. Cost Management & Teardown

All recommended services (Vercel, Netlify, Render Free Web Service, and Neon Free Serverless Postgres) operate at **$0.00/month** within their free tier allowances.

To cleanly decommission the deployment:
1. **Neon:** In the Neon console, delete the `bankflow-portfolio` project.
2. **Render:** In the Render dashboard, navigate to `bankflow-reporting-api` -> **Settings** -> **Delete Web Service**.
3. **Vercel / Netlify:** Delete the imported project from your account dashboard.
