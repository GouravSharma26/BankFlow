# BankFlow — Technical Decisions and Decision Log

> This file records the current choices and the reason for them. A decision is not final until it is implemented, tested, and confirmed in the repository. Keep this log short enough to review, but specific enough that an engineer can understand trade-offs.

## 1. Current Planned Decisions

| ID | Topic | Current choice | Status | Reason / guardrail |
|---|---|---|---|---|
| TD-001 | Primary language | Python 3.12+ | Planned | Familiar ecosystem for ETL and testability; choose an actually supported version after dependency/environment check. |
| TD-002 | Warehouse database | PostgreSQL | Planned | Relational constraints, transactions, views, and query analysis are central to the learning goal. |
| TD-003 | Input format | CSV | Planned | Easy to inspect, generate, version as small fixtures, and explain in a demo. |
| TD-004 | Monetary representation | Python `Decimal` + PostgreSQL `NUMERIC` | Required design rule | Avoid binary floating-point rounding in monetary calculations. |
| TD-005 | Testing | pytest | Planned | Allows unit, database integration, and end-to-end verification. |
| TD-006 | CI | GitHub Actions | Planned | Makes tests visible and repeatable on code changes. |
| TD-007 | Dashboard | Choose Power BI or Metabase | Open | Decide once based on environment/access; do not build both in MVP. |
| TD-008 | Python DB access | Choose SQLAlchemy or psycopg | Open | Pick one primary approach after deciding how migrations/schema initialization will be handled. |
| TD-009 | Orchestration | Manual CLI first | Planned | Prove correctness before introducing scheduler complexity. |
| TD-010 | Containerization | Docker Compose optional after local success | Deferred | Add only if it makes clean setup materially easier. |
| TD-011 | Data content | Synthetic records only | Mandatory | Prevent privacy and security risks; no live systems or customer records. |
| TD-012 | Warehouse model | Dimensional star schema | Planned | Clear analytical model with fact/dimension relationships. |
| TD-013 | Event replay | Database-enforced idempotency | Mandatory | Prevent duplicate facts even across repeated/concurrent attempts. |
| TD-014 | Currency reporting | One currency for simplest MVP or grouped currencies | Open/configurable | Never sum incomparable currencies without an explicit conversion model. |
| TD-015 | Batch status | Explicit lifecycle states persisted in monitoring | Planned | Make process state and failure/recovery outcomes inspectable. |

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

No technical decision should be called implemented until the codebase and tests demonstrate it. As implementation starts, replace the `Planned` status for a row only after verifying the actual package/configuration/schema in Git. Record material deviations below.

_No implementation-specific decision records yet._
