# BankFlow — Banking Transaction ETL & Analytics Warehouse

> **Status: Planning / implementation not yet started.** This README describes the intended MVP. Feature claims must be updated only after the corresponding code, tests, and evidence exist.

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

## Planned technology stack

| Area | Planned choice |
|---|---|
| Language | Python 3.12+ |
| Database | PostgreSQL |
| Data processing | Python; Pandas where useful |
| Database access | Choose SQLAlchemy or psycopg during foundation phase |
| Testing | pytest |
| Version control | Git and GitHub |
| CI | GitHub Actions |
| Dashboard | Choose Power BI or Metabase; do not implement both for the MVP |

These are planned choices, not evidence that implementation is complete. See `docs/design_decisions.md` for decision status.

## Planned repository layout

```text
BankFlow/
├── AGENTS.md
├── README.md
├── plan.md
├── HUMAN_SETUP.md
├── DEVELOPMENT_CHECKLIST.md
├── REVIEW_WORKFLOW.md
├── PHASE_LOG.md
├── docs/
│   ├── architecture.md
│   ├── data_contract.md
│   ├── design_decisions.md
│   └── testing_strategy.md
├── src/bankflow/
├── sql/
├── tests/
├── data/samples/
└── .github/workflows/
```

The actual layout may be refined during Phase 1, but changes must be documented and kept consistent across the repo.

## Project status

No feature should be marked complete just because it is described in documentation. The current state should be checked in `DEVELOPMENT_CHECKLIST.md` and `PHASE_LOG.md`.

## Future setup

Implementation setup instructions will be validated and added as Phase 1 selects the actual package manager, database configuration method, and project layout. Start with `HUMAN_SETUP.md` and follow the phase process in `REVIEW_WORKFLOW.md`.
