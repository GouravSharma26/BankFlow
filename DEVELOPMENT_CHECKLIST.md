# BankFlow — Development Checklist and Phase Gates

> **Rule:** Work on one phase at a time. A phase is complete only when its exit criteria are verified, documentation is updated, a phase-log entry is recorded, and the requested GitHub handoff is attempted truthfully.

Status key: `NOT STARTED` · `IN PROGRESS` · `BLOCKED` · `VERIFIED`

Initial status for all implementation phases: **NOT STARTED**. Documentation preparation is not implementation completion.

## Phase 0 — Repository Baseline and Agent Alignment (Status: VERIFIED)

**Goal:** Make the project instructions and GitHub workflow reliable before code is written.

- [x] Inspect repository contents, current Git status, current branch, and remote URL.
- [x] Verify the expected GitHub remote is `https://github.com/GouravSharma26/BankFlow.git` or the equivalent HTTPS URL without `.git`.
- [x] Preserve the existing `plan.md`; do not regenerate or overwrite it unnecessarily.
- [x] Ensure all supporting docs are present and internally consistent.
- [x] Establish the initial baseline branch/commit if the repository has no code history.
- [x] Push the baseline to GitHub if credentials and permissions permit.
- [x] Record baseline commit, push status, and any permission blocker in `PHASE_LOG.md`.

**Exit criteria:** A clean repository baseline contains the plan and agent workflow docs, and the GitHub status is explicitly recorded. This phase does not mark application code complete.

## Phase 1 — Python Foundation, Synthetic Generator, and Staging (Status: VERIFIED)

**Goal:** Generate repeatable synthetic source files and ingest them into a PostgreSQL staging layer.

- [x] Finalize Python/package/dependency choices and document them.
- [x] Create `pyproject.toml`, source package, test layout, `.gitignore`, and `.env.example`.
- [x] Create safe local configuration and database connection handling.
- [x] Create source data contracts for customers, accounts, branches, and transactions.
- [x] Implement synthetic generator with fixed seed, configurable volume, dates, and defect scenarios.
- [x] Create database schema initialization for staging and batch metadata.
- [x] Implement file-level header/format checks and staging ingestion.
- [x] Capture source file, row number, batch ID, and ingest timestamp.
- [x] Add initial unit and database smoke tests.
- [x] Update setup instructions using verified commands.

**Exit criteria:** From a clean local setup, the developer can generate a small synthetic dataset, initialize the database, ingest it to staging, and inspect row/batch counts. At least one automated test verifies the path.

## Phase 2 — Validation, Quarantine, and Data Contracts (Status: REVIEW PENDING)

**Goal:** Make accepted/rejected outcomes explicit and reproducible.

- [x] Implement stable validation rule codes.
- [x] Validate required fields, amount parsing, timestamps, supported values, currency, and references.
- [x] Distinguish file-level failures from row-level rejects.
- [x] Preserve source values needed to diagnose bad records.
- [x] Record issue severity, rule code, source row, batch, and useful reason.
- [x] Ensure malformed input does not disappear silently.
- [x] Add tests for each injected defect and expected disposition.
- [x] Update `docs/data_contract.md` and data dictionary.

**Exit criteria:** A mixed-quality dataset is processed deterministically; each tested defect produces the expected issue/outcome and the batch row accounting is explainable. (Verified: 46 automated tests pass with zero skips/failures against bankflow_test, including lifecycle guards, cross-batch reference restrictions, uniqueness, currency consistency, and duplicate historical exclusion. External review approval remains pending).


## Phase 3 — Warehouse Model, Loading, Idempotency, and Reconciliation

**Goal:** Load valid records to a dimensional PostgreSQL warehouse safely.

- [ ] Create dimension tables for customer, account, branch, date, and transaction type as required by the plan.
- [ ] Create `fact_transactions` with documented transaction grain and source lineage.
- [ ] Define stable business-event identity and enforce uniqueness in PostgreSQL.
- [ ] Load dimensions before facts and resolve dimension keys explicitly.
- [ ] Use database transactions for logically related warehouse changes.
- [ ] Implement replay-safe loading/upsert behavior and clear insert/update/skip counts.
- [ ] Handle transaction statuses, reversals, currency, and late arrivals according to documented semantics.
- [ ] Implement batch state transitions and machine-/human-readable summaries.
- [ ] Implement count and, where comparable, value reconciliation.
- [ ] Add integration and replay tests.

**Exit criteria:** A valid mixed batch populates the warehouse; the same event/file can be replayed without duplicate facts; a forced load failure does not leave an invalid partial warehouse state; reconciliation matches the defined contract.

## Phase 4 — SQL Analytics and Metric Definitions

**Goal:** Deliver reliable analytics whose definitions are documented and repeatable.

- [ ] Implement daily activity query.
- [ ] Implement deposit-versus-withdrawal query with explicit event/status semantics.
- [ ] Implement branch/channel analysis.
- [ ] Implement data-quality issue reports.
- [ ] Implement ETL run/pipeline reports.
- [ ] Create reporting views where useful.
- [ ] Add indexes only when query use or measurements justify them.
- [ ] Inspect relevant query plans and save reproducible examples where useful.
- [ ] Document definitions, filters, currency rules, and known limitations.
- [ ] Compare query output to expected fixture results.

**Exit criteria:** Required SQL reports run against known test data and return verified results; metric definitions prevent misleading totals.

## Phase 5 — Dashboard

**Goal:** Present the verified warehouse outputs in a simple, understandable dashboard.

- [ ] Choose one tool: Power BI or Metabase.
- [ ] Connect to the reporting layer using a read-only reporting role where practical.
- [ ] Build overview page.
- [ ] Build transaction analysis page.
- [ ] Build pipeline/data-quality page.
- [ ] Add appropriate date, branch, channel, and transaction-type filters.
- [ ] Label units, currencies, filters, and statuses clearly.
- [ ] Compare displayed metric values against direct SQL outputs.
- [ ] Save redacted screenshots or a short demo sequence.

**Exit criteria:** Dashboard data matches authoritative SQL queries for selected test cases and displays metric semantics/units clearly.

## Phase 6 — Hardening, CI, Documentation, and Portfolio Release

**Goal:** Make the project easy to test, review, reproduce, and explain.

- [ ] Complete unit, PostgreSQL integration, end-to-end, and relevant failure-injection tests.
- [ ] Ensure the test database is separate and the test runner guards against unsafe targets.
- [ ] Add GitHub Actions workflow for tests and any configured lint/format checks.
- [ ] Verify configuration and secret-handling hygiene.
- [ ] Run `git diff --check` and inspect all tracked changes.
- [ ] Verify clean-clone installation and run instructions.
- [ ] Finalize README, architecture, data contract/dictionary, testing, and decision documentation.
- [ ] Measure actual runtime on a documented dataset only if reporting performance.
- [ ] Record known limitations, setup requirements, and optional extensions.
- [ ] Prepare interview explanation and reproducible demo.

**Exit criteria:** A reviewer can follow the repository instructions to generate synthetic data, run the ETL, inspect rejects and warehouse output, reproduce SQL reports, run tests, and understand limitations without undocumented manual steps.

## Phase Completion Template

Copy this block into `PHASE_LOG.md` after each phase:

```markdown
### Phase N — <name>
- Status: VERIFIED / BLOCKED
- Date:
- Commit:
- Branch:
- GitHub push: pushed / blocked (reason)
- Scope delivered:
- Verification commands:
- Test results:
- Acceptance evidence:
- Known limitations:
- Reviewer findings:
- Follow-up items:
```

## Global Rules

- Do not start Phase N+1 until Phase N's acceptance criteria have passed or the user explicitly approves proceeding with a documented exception.
- Do not claim an untested metric, performance gain, or feature.
- Do not commit real financial/customer data, secrets, `.env`, database dumps, virtual environments, or large generated files.
- Every feature must have appropriate tests and matching documentation.
