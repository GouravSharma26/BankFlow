# BankFlow — Human Setup Guide

> This guide is for the developer coordinating implementation in Antigravity. It deliberately distinguishes generic prerequisites from commands that should be finalized only after the project skeleton is implemented.

## 1. Current repository state

BankFlow is a fully verified, runnable Python 3.12 and PostgreSQL CLI ETL and analytics warehouse for synthetic banking data. The implemented and tested core includes:
- Staging ingestion with source lineage preservation.
- Rule-based contract validation and quarantined record tracking.
- Conformed dimensional warehouse loading with date, transaction type, branch, customer, and account dimensions, and transaction facts.
- Idempotent replay safety distinguishing identical replays from conflicting payloads with concurrency protection.
- End-to-end reconciliation auditing records and monetary balances.
- Repeatable SQL analytics pack for transaction volume, channel/type mix, branch metrics, batch health, and quarantine analysis.

Cloud scheduling, managed cloud hosting, and BI dashboards (Power BI / Metabase) are deferred follow-up items.

GitHub repository: <https://github.com/GouravSharma26/BankFlow>

## 2. Prerequisites

Install and verify these tools before beginning the implementation phase:

- Git, with your GitHub identity configured.
- Python 3.12 or another Python version explicitly selected by the project after checking dependency compatibility.
- PostgreSQL supported by the chosen local environment.
- A code editor/Antigravity with access to the local BankFlow folder.
- Optional later: Power BI Desktop or Metabase, depending on the dashboard choice.

Useful checks from a terminal:

```bash
git --version
python --version
python -m pip --version
psql --version
```

The `psql` command may not be available even if PostgreSQL is installed; verify the installation path and PATH configuration before assuming the database server is missing.

## 3. Open the project in Antigravity

1. Open the local `BankFlow` repository folder, not just a single Markdown file.
2. Confirm `plan.md` is at the repository root.
3. Confirm `AGENTS.md`, `DEVELOPMENT_CHECKLIST.md`, and the files under `docs/` are also at the root/docs locations shown in the README.
4. Ask Antigravity to read `AGENTS.md` and `plan.md` before making code changes.
5. Ask it to inspect `git status`, `git remote -v`, the current branch, and the repository contents before modifying anything.
6. If GitHub is not initialized/configured locally, establish the baseline according to `REVIEW_WORKFLOW.md`.

## 4. Environment configuration principles

The actual configuration keys must be derived from the chosen implementation. Do not invent environment variables before deciding what needs them. At minimum, the database connection should be supplied through an environment variable such as `DATABASE_URL` or clearly documented discrete settings.

- Commit `.env.example` containing placeholders only.
- Keep `.env` in `.gitignore`.
- Do not put secrets in source code, logs, screenshots, README files, or Antigravity prompts.
- Do not place real banking/customer data in the repository.
- The integration test database must be separate from the developer database.

## 5. Windows setup notes

On Windows, create a virtual environment using the Python launcher or the installed Python executable. A typical pattern is:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,api]"
```

If PowerShell blocks virtual-environment activation, use an allowed terminal configuration or invoke the virtual environment's Python directly. Do not weaken machine-wide execution policies just to run this project.

### Verified execution commands:

1. **Configure environment (.env):**
   ```powershell
   # If you do not already have a .env file:
   Copy-Item .env.example .env
   ```
   *Important:* Create `.env` and set the intended host port **before** starting Docker Compose.
   If host port 5432 is already occupied by a local Windows PostgreSQL service, set `BANKFLOW_DB_PORT=5433` in your `.env`.
   If you already have a working `.env`, do not overwrite it.

2. **Start PostgreSQL with Docker Compose (Recommended):**
   ```powershell
   docker compose up -d
   ```
   *Note:* Starts PostgreSQL 17 on loopback `127.0.0.1:${BANKFLOW_DB_PORT:-5432}` and automatically creates both `bankflow` and `bankflow_test` databases via `docker/01-init-test-db.sql` upon initial volume creation.

   > [!CAUTION]
   > Do **not** run `docker compose down -v` to troubleshoot ordinary connection issues. The `-v` flag removes the persistent volume (`bankflow_postgres_data`) and deletes your local databases.
   >
   > The initialization script `docker/01-init-test-db.sql` runs only when PostgreSQL initializes a brand-new data directory. If you change credentials after the volume exists, updating `.env` alone will not alter the existing database user's password.

3. **Run tests:**
   ```powershell
   python -m pytest tests -v
   ```

4. **Verify database connectivity:**
   ```powershell
   python -m bankflow test-connection
   python -m bankflow test-connection --test-db
   ```

5. **Initialize PostgreSQL database schemas:**
   ```powershell
   python -m bankflow init-db
   ```

6. **Generate synthetic data:**
   ```powershell
   python -m bankflow generate --output-dir data/samples --seed 42 --branches 5 --customers 25 --accounts 40 --transactions 100
   ```

7. **Run end-to-end batch ETL:**
   ```powershell
   python -m bankflow run --input-dir data/samples --batch-id demo-001
   ```
   *Or execute granular lifecycle stages:*
   ```powershell
   python -m bankflow stage --input-dir data/samples --batch-id demo-001
   python -m bankflow validate demo-001
   python -m bankflow load demo-001
   python -m bankflow reconcile demo-001
   ```

8. **Inspect batch metrics and status:**
   ```powershell
   python -m bankflow batch-status demo-001
   ```

9. **Run analytics query pack:**
   ```powershell
   psql "postgresql://postgres:postgres@localhost:5432/bankflow" -v ON_ERROR_STOP=1 -f sql/04_analytics_queries.sql
   ```

10. **Provision least-privilege reporting role:**
    Create the reporting role using the schema script:
    ```powershell
    psql "postgresql://postgres:postgres@localhost:5432/bankflow" -f sql/06_reporting_role.sql
    ```
    Set the password securely out-of-band:
    - **Local setup (interactive psql - recommended):**
      Connect interactively via `psql "postgresql://postgres:postgres@localhost:5432/bankflow"` and run:
      ```sql
      \password bankflow_reporting_user
      ```
      This prompts for the new password without terminal command echoing or process-table exposure.
    - **Automated deployments:**
      Retrieve credentials securely from a secret manager (e.g. AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault) and provision using a non-echoing deployment pipe or secret engine. Never expose passwords in command-line arguments.

    Configure credentials together (both must be non-empty):
    ```powershell
    # In PowerShell session:
    $env:BANKFLOW_REPORTING_DB_USER = "bankflow_reporting_user"
    $env:BANKFLOW_REPORTING_DB_PASSWORD = "your_secure_password"
    ```
    Or configure in `.env`:
    ```bash
    BANKFLOW_REPORTING_DB_USER=bankflow_reporting_user
    BANKFLOW_REPORTING_DB_PASSWORD=your_secure_password
    ```
    *Note: If neither is set, local development safely defaults to the standard database connection.*


11. **Start read-only Reporting API:**
    ```powershell
    python -m bankflow serve --host 127.0.0.1 --port 8000
    ```
    *API Documentation:* Explore interactive OpenAPI documentation at `http://127.0.0.1:8000/docs`.

12. **Connect Lovable Analytics Console:**
    Configure the web application environment variable:
    ```bash
    VITE_BANKFLOW_API_BASE_URL=http://localhost:8000
    ```
    *Refer to `docs/dashboard_api_contract.md` for complete API and integration specifications.*

## 6. PostgreSQL safety checklist

Before running migrations or tests:

- Identify the exact database host, database name, and role being used.
- Never run destructive setup/teardown against a database whose role is unclear.
- Create a dedicated database for automated integration tests.
- Use synthetic seed data only.
- Ensure the application refuses to run destructive test setup when the configured database is not recognized as the test database.

## 7. First-session instruction for Antigravity

Use a prompt like this:

> Read `AGENTS.md`, `plan.md`, `DEVELOPMENT_CHECKLIST.md`, `docs/architecture.md`, `docs/data_contract.md`, `docs/design_decisions.md`, and `docs/testing_strategy.md`. The repository is at the planning stage. Do not implement the entire project in one pass. Inspect the Git repository and environment first, then execute only the first unchecked phase in `DEVELOPMENT_CHECKLIST.md`. Define the acceptance criteria, implement the smallest working increment, test it, update documentation and `PHASE_LOG.md`, and follow `REVIEW_WORKFLOW.md` for the GitHub handoff. Do not begin the following phase without a completed handoff.

## 8. Troubleshooting approach

When a setup command fails:

1. Preserve the full error output.
2. Check the executable/version, current working directory, environment variables, and database target.
3. Identify the root cause before changing code or project dependencies.
4. Make the smallest change that addresses the cause.
5. Record the verified fix in README or a troubleshooting section so the same problem is not rediscovered.

Do not mask environment problems by disabling tests or deleting configuration files.
