# BankFlow — Banking Transaction ETL & Analytics Warehouse

> **Status: Phase 1 Implemented & Verified.** The Python foundation, deterministic synthetic data generator, Docker Compose PostgreSQL 17 environment, staging schema, and batch ingestion are implemented and verified with automated unit and integration tests.
>
> **Future Work:** The validation & quarantine engine ([Phase 2](DEVELOPMENT_CHECKLIST.md)), dimensional warehouse ([Phase 3](DEVELOPMENT_CHECKLIST.md)), analytics & reconciliation queries ([Phase 4](DEVELOPMENT_CHECKLIST.md)), and BI dashboard ([Phase 5](DEVELOPMENT_CHECKLIST.md)) are planned future phases.

BankFlow is an educational data-engineering project that uses **synthetic banking data only** to demonstrate how raw transaction files can be ingested, validated, transformed, loaded into a PostgreSQL dimensional warehouse, reconciled, and used for analytics.

It is designed as a portfolio project for entry-level Data Engineer, Data Analyst, and Software Application Analyst roles.

## Project goals

- Build a repeatable Python batch ETL pipeline.
- Preserve raw/staging records and explicitly report invalid data.
- Design PostgreSQL staging, monitoring, dimensional warehouse, and reporting layers.
- Make warehouse loading idempotent and transaction-safe.
- Reconcile source, accepted, rejected, and loaded records under documented rules.
- Build reproducible SQL analytics and a small data-quality/dashboard experience.
- Provide automated tests, CI, clear documentation, and a clean-clone setup.

## Safety and scope

BankFlow is a simulation, **not a real banking application**. It will not connect to bank systems, move money, make actual financial decisions, or use real customer/account data. Use synthetic datasets only.

## Documentation map

- [`plan.md`](plan.md) — master requirements, detailed data model, ETL rules, roadmap, and acceptance criteria.
- [`AGENTS.md`](AGENTS.md) — mandatory instructions for Antigravity/coding agents, including phase and GitHub handoff rules.
- [`HUMAN_SETUP.md`](HUMAN_SETUP.md) — developer environment and safe setup instructions.
- [`DEVELOPMENT_CHECKLIST.md`](DEVELOPMENT_CHECKLIST.md) — phase-by-phase tasks and exit criteria.
- [`REVIEW_WORKFLOW.md`](REVIEW_WORKFLOW.md) — commit/push process and how to request a phase review.
- [`PHASE_LOG.md`](PHASE_LOG.md) — evidence-based record of completed phases and review findings.
- [`docs/architecture.md`](docs/architecture.md) — component boundaries and data flow.
- [`docs/data_contract.md`](docs/data_contract.md) — source fields, semantics, and validation contract.
- [`docs/design_decisions.md`](docs/design_decisions.md) — current technology choices and decision log.
- [`docs/testing_strategy.md`](docs/testing_strategy.md) — unit, integration, end-to-end, and failure testing requirements.

## Technology stack & status

| Area | Component | Status | Notes |
|---|---|---|---|
| Language | Python 3.12+ | Implemented (Phase 1) | Package configured with `pyproject.toml` |
| Database | PostgreSQL 17 | Implemented (Phase 1) | Local Docker Compose setup (`127.0.0.1:5432`/`5433`) |
| DB Driver | `psycopg2-binary` | Implemented (Phase 1) | Connection handling and transactional contexts |
| Data Generator | Synthetic Generator CLI | Implemented (Phase 1) | Fixed-seed deterministic generator with date ranges & defect scenarios |
| Staging & Monitoring | PostgreSQL staging schema | Implemented (Phase 1) | `monitoring.etl_batch_runs` and `staging.stg_*` tables |
| Staging Ingestion | `bankflow stage` | Implemented (Phase 1) | Validates CSV headers and stages raw payloads with lineage |
| Validation Engine | Validation & Quarantine | Planned (Phase 2) | Data-contract rule enforcement & quarantine tables |
| Warehouse | Dimensional Models (Star Schema)| Planned (Phase 3) | Idempotent warehouse loading & SCD Type 2 dimensions |
| Reconciliation | Count/Value Audits | Planned (Phase 4) | Ingestion-to-warehouse reconciliation reports |
| Analytics & Reports | Reporting Views & Queries | Planned (Phase 4) | Monthly volumes, high-value transfers, fee analyses |
| Dashboard | BI Dashboard & CI | Planned (Phase 5) | Metabase / Power BI dashboard and GitHub Actions CI |

## Repository layout

```text
BankFlow/
├── .env.example              # Sample configuration template with safety guards
├── docker-compose.yml        # PostgreSQL 17 service with persistent storage
├── docker/
│   └── 01-init-test-db.sql   # Creates dedicated bankflow_test database
├── pyproject.toml            # Python packaging and dependency declarations
├── src/bankflow/
│   ├── __init__.py
│   ├── __main__.py           # CLI entry point (generate, stage, init-db, test-connection)
│   ├── config.py             # Environment configuration & test database safety guards
│   ├── constants.py          # Data contract columns, defect codes, domain values
│   ├── db.py                 # Safe database connections & transaction managers
│   ├── generator/
│   │   ├── defects.py        # Configurable defect injection scenarios
│   │   └── generator.py      # Deterministic synthetic data generator with date boundaries
│   └── staging/
│       ├── loader.py         # CSV header validation, DictReader binding, staging ingestion
│       └── schema.py         # DDL execution for staging and monitoring schemas
├── sql/
│   └── 01_staging_schema.sql # DDL for monitoring and staging schemas
├── tests/
│   ├── test_config.py        # Database configuration and test safety guardrail tests
│   ├── test_generator.py     # Determinism, inclusive date ranges, and defect scenarios
│   ├── test_staging_validation.py # Header whitespace, ordering, andDictReader corruption guards
│   └── test_db_integration.py # PostgreSQL schema init, staging, and batch collision tests
├── docs/                     # Architecture, data contracts, design decisions, and testing
├── DEVELOPMENT_CHECKLIST.md  # Phase-by-phase implementation checklist
├── HUMAN_SETUP.md            # Local developer setup and execution commands
├── PHASE_LOG.md              # Historical evidence log and review resolutions
├── plan.md                   # Canonical system specifications and scope
└── README.md
```

## Quickstart

Follow [`HUMAN_SETUP.md`](HUMAN_SETUP.md) for full developer environment setup.

```powershell
# 1. Start PostgreSQL with Docker Compose
docker compose up -d

# 2. Test database connectivity
python -m bankflow test-connection
python -m bankflow test-connection --test-db

# 3. Initialize staging schema
python -m bankflow init-db

# 4. Generate synthetic dataset with date ranges
python -m bankflow generate --output-dir data/samples --start-date 2026-01-01 --end-date 2026-01-31 --seed 42 --transactions 100

# 5. Ingest dataset into staging
python -m bankflow stage --input-dir data/samples

# 6. Run automated test suite
python -m pytest tests -v
```
