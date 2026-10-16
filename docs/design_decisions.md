# BankFlow — Technical Decisions and Decision Log

> This file records the current choices and the reason for them. A decision is not final until it is implemented, tested, and confirmed in the repository. Keep this log short enough to review, but specific enough that an engineer can understand trade-offs.

## 1. Current Planned Decisions

| ID | Topic | Current choice | Status | Reason / guardrail |
|---|---|---|---|---|
| TD-001 | Primary language | Python 3.12+ | Accepted | Standard ecosystem for ETL and testability; running Python 3.12.6. |
| TD-002 | Warehouse database | PostgreSQL | Accepted | Relational constraints, transactions, views, and query analysis are central to the learning goal. |
| TD-003 | Input format | CSV | Accepted | Easy to inspect, generate, version as small fixtures, and explain in a demo. |
| TD-004 | Monetary representation | Python `Decimal` + PostgreSQL `NUMERIC` | Accepted | Avoid binary floating-point rounding in monetary calculations. |
| TD-005 | Testing | pytest | Accepted | Allows unit, database integration, and end-to-end verification. |
| TD-006 | CI | GitHub Actions | Planned | Makes tests visible and repeatable on code changes. |
| TD-007 | Dashboard | Choose Power BI or Metabase | Open | Decide once based on environment/access; do not build both in MVP. |
| TD-008 | Python DB access | psycopg2-binary | Accepted | Direct, high-performance SQL execution and batch staging with zero ORM overhead. |
| TD-009 | Orchestration | Manual CLI first (Click) | Accepted | Prove correctness before introducing scheduler complexity. |
| TD-010 | Containerization | Docker Compose for local PostgreSQL | Accepted | Provides one-command local PostgreSQL 17 setup with primary and test databases. |
| TD-011 | Data content | Synthetic records only | Accepted | Prevent privacy and security risks; no live systems or customer records. |
| TD-012 | Warehouse model | Dimensional star schema | Planned | Clear analytical model with fact/dimension relationships. |
| TD-013 | Event replay | Database-enforced idempotency | Mandatory | Prevent duplicate facts even across repeated/concurrent attempts. |
| TD-014 | Currency reporting | One currency for simplest MVP or grouped currencies | Open/configurable | Never sum incomparable currencies without an explicit conversion model. |
| TD-015 | Batch status | Explicit lifecycle states persisted in monitoring | Accepted | Make process state and failure/recovery outcomes inspectable. |

## 2. Decision-Making Rules

For each new technology or non-trivial alternative, document:

1. Problem or requirement that prompts the decision.
2. Options considered, including the simplest option.
3. Chosen option and why it fits this project's size and timeline.
4. Impact on testability, setup, data correctness, and ongoing maintenance.
5. Whether this is required for MVP or deferred.
6. The date/phase and evidence that validated the choice.

Do not add a tool because it appears on job descriptions alone. A tool should solve a specific problem and be demonstrable in the code.

## 3. Explicit MVP Guardrails

- No Kafka, Spark, Airflow, or distributed architecture before the core batch ETL is correct.
- No cloud deployment required for MVP.
- No external AI/LLM service is needed for this project.
- No real bank/customer data or live banking API.
- No unmeasured claims such as “optimized by 40%”.
- No currency conversion until a real, clearly synthetic FX-rate model and reporting rule are defined.
- No account balance calculations by naively summing every event amount.

## 4. Decision Log Template

Append entries below rather than silently changing an existing decision.

```markdown
### TD-<number> — <title>
- Date / phase:
- Status: Proposed / Accepted / Superseded
- Context:
- Options considered:
- Decision:
- Rationale:
- Consequences / trade-offs:
- Verification or evidence:
- Supersedes (if applicable):
```

## 5. Actual Implementation Updates

### TD-008 — PostgreSQL Access via psycopg2-binary
- Date / phase: 2026-10-16 / Phase 1
- Status: Accepted
- Context: BankFlow needs a robust, parameterized database access layer for PostgreSQL schema initialization, high-volume batch staging, and transactional execution.
- Options considered:
  1. SQLAlchemy Core / ORM: flexible multi-dialect abstraction, but introduces additional layers, migration overhead, and extra dependencies.
  2. psycopg2-binary: established Python-PostgreSQL driver, native support for batch operations (`execute_batch`), transactions, and parameterized SQL without ORM magic.
  3. psycopg (v3): modern rewrite, but psycopg2-binary is already pre-installed in the local environment and provides battle-tested stability.
- Decision: Select `psycopg2-binary>=2.9.0` as the primary database driver.
- Rationale: Staging and data warehousing rely on explicit relational SQL, schemas, and transactions. An ORM is not needed and adds complexity for batch ETL.
- Consequences / trade-offs: SQL statements are written explicitly in `.sql` files and Python constants, which maximizes transparency and learning value for SQL analytics.
- Verification or evidence: Database connection module (`bankflow.db`), schema initializer (`bankflow.staging.schema`), and staging loader (`bankflow.staging.loader`) successfully verified in tests.

### TD-010 — Local PostgreSQL via Docker Compose
- Date / phase: 2026-10-16 / Phase 1
- Status: Accepted
- Context: Local PostgreSQL installation may have variable authentication configs, existing services, or credential mismatches that make onboarding and integration testing difficult across different developer machines.
- Options considered:
  1. Rely solely on host-installed PostgreSQL service.
  2. Provide a declarative `docker-compose.yml` for PostgreSQL 17 with an automated test database initialization script.
- Decision: Provide `docker-compose.yml` with `postgres:17-alpine`, persistent volume `bankflow_postgres_data`, and initialization script `docker/01-init-test-db.sql`.
- Rationale: Gives an instant, repeatable, reproducible local database environment for both the primary warehouse (`bankflow`) and the test database (`bankflow_test`), with configurable port mapping to avoid host collisions.
- Consequences / trade-offs: Requires Docker Desktop or Docker engine, but developers without Docker can still point to any existing PostgreSQL instance via `.env`.
- Verification or evidence: `docker compose config` validates cleanly. Container startup and healthchecks verified.
