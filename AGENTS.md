# BankFlow — Agent Instructions

> This file governs how Antigravity or another coding agent should work in this repository.
> The project is currently planned/inception-stage. Do not claim implementation features exist until code and tests prove they do.

## 1. Required Reading Before Every Phase

Before editing code, read these files in this order:

1. `AGENTS.md` — operating rules for the coding agent.
2. `plan.md` — canonical project scope, data model, ETL behavior, acceptance criteria, and roadmap.
3. `DEVELOPMENT_CHECKLIST.md` — the phase currently in progress and its exit criteria.
4. `docs/architecture.md` — system boundaries and data flow.
5. `docs/data_contract.md` — source data semantics and validation contract.
6. `docs/design_decisions.md` — chosen tools and constraints.
7. `docs/testing_strategy.md` — required tests and evidence.
8. `HUMAN_SETUP.md` and `REVIEW_WORKFLOW.md` when environment, Git, or phase handoff is relevant.

If these files conflict, `plan.md` defines the project requirements. Record material conflicts in `PHASE_LOG.md` and make the smallest safe choice consistent with the plan. Do not silently expand scope.

## 2. Product Goal

Build BankFlow, a reproducible educational batch ETL and analytics warehouse using synthetic banking data only. The system must demonstrate:

- Python-based ingestion, validation, transformation, and loading.
- PostgreSQL staging, monitoring, dimensional warehouse, and reporting layers.
- Explicit data-quality rules and quarantine/rejection records.
- Database-enforced idempotency and transaction-safe loading.
- Count/value reconciliation with traceable batch outcomes.
- SQL analytics, a small dashboard, automated tests, CI, and reproducible documentation.

This is a portfolio simulation. Do not connect to real banking systems or use real financial/customer data.

## 3. Phase Discipline — Mandatory

- Work on **one phase at a time**. Do not start the next phase until the current phase's exit criteria pass and its handoff is recorded.
- Begin a phase by stating the phase goal, expected files/changes, and acceptance criteria in the task summary.
- Inspect the current repository and Git status before editing. Preserve existing user work.
- Implement the smallest coherent change that satisfies the current phase. Avoid speculative abstractions and optional extensions.
- Run focused tests during development, then all applicable tests for the phase.
- Update `DEVELOPMENT_CHECKLIST.md`, `PHASE_LOG.md`, README, and technical documentation when the implementation changes the documented behavior.
- Finish with a concise report: changes made, commands run, test results, known limitations, Git commit/branch, push status, and the exact next phase. Distinguish verified facts from assumptions.
- Do not mark a checklist item complete unless its acceptance evidence exists.

## 4. Phase Completion, Commit, and GitHub Push

The user has explicitly requested that each completed phase be pushed to `https://github.com/GouravSharma26/BankFlow` and then reviewed. Treat this as the expected phase handoff:

1. Run applicable tests and inspect their output.
2. Run formatting/lint checks if they are configured.
3. Review `git diff`, `git diff --check`, and `git status`; check for accidental generated files, secrets, raw real data, and unrelated edits.
4. Update the checklist and add a phase entry to `PHASE_LOG.md` with the result evidence.
5. Create a focused commit using a descriptive message, e.g. `feat(etl): add batch staging and validation`.
6. Push the completed phase to the user's GitHub repository. Prefer a phase branch named `phase/<number>-<slug>` and do not force-push. Do not delete or overwrite remote history.
7. If the repository is still empty or a default branch does not exist, establish the initial baseline as `main` first. Keep the initial documentation baseline separate from implementation changes.
8. If Git credentials, network, branch protection, or repository permissions prevent the push, do **not** claim success. Keep the local commit, report the precise blocker, and provide the exact command the user should run.
9. Never bypass GitHub protections, publish secrets, or force-push. Never commit `.env`, credentials, tokens, real customer data, a local database, or large generated datasets.
10. Do not merge a phase branch automatically if a pull request workflow is being used. Leave it available for review unless the user explicitly requests merging.

Use the remote configured in the existing repository if correct. If none exists, verify with `git remote -v` and add only the expected remote URL. Do not replace a different valid remote without explaining the issue.

## 5. Required Engineering Practices

### Python
- Prefer small, typed, single-purpose functions with useful names.
- Add type hints where they improve clarity; use clear docstrings for public interfaces.
- Use explicit exceptions and useful error messages. Avoid broad `except Exception: pass` patterns.
- Keep business rules out of CLI parsing and I/O code where practical.
- Use a fixed-seed synthetic generator so fixtures can be reproduced.

### SQL and data correctness
- Use PostgreSQL constraints to enforce key correctness rules.
- Use parameterized SQL; never build query strings from untrusted values.
- Use `NUMERIC`/`Decimal` for monetary amounts, not floating-point types.
- Define timezone, transaction-status, reversal, currency, and duplicate-event semantics explicitly.
- Keep raw/staging values available enough to explain rejected records.
- Never silently discard bad rows. Record stable rule codes and reasons.
- Make warehouse event idempotency enforced by a unique key/constraint, not only an in-memory check.
- Load related warehouse data transactionally and do not mark a batch successful before the load commits.
- Do not aggregate currencies together without grouping by currency or implementing an explicitly documented conversion model.

### Security and privacy
- Use synthetic data only. Avoid generating unnecessary personal attributes.
- Do not commit `.env` files, passwords, tokens, production records, or database dumps.
- Keep `.env.example` limited to placeholder values and document required environment variables.
- Integration tests must use a dedicated test database, never the development or production database.
- Never use destructive commands against a configured database without confirming its target and necessity.

### Scope control
- No live bank integrations, payment execution, real fraud claims, or real customer data.
- No Kafka, Spark, Airflow, cloud infrastructure, Oracle, or additional frameworks in the MVP unless the relevant checklist phase explicitly includes the extension.
- Do not add dependencies unless necessary; explain any new dependency in `docs/design_decisions.md`.
- Do not claim performance improvements without a reproducible baseline and measurements.

## 6. Test and Evidence Rules

- Identify which test layer each new test belongs to: unit, PostgreSQL integration, or end-to-end.
- A successful import or a running app alone is not sufficient evidence of correctness.
- Cover happy paths, malformed input, missing references, duplicates/replays, database failures where feasible, and rollback behavior.
- Report tests that could not run and why. Do not relabel skipped or blocked tests as passed.
- If a test fails, fix it or document the precise blocker before considering the phase done.
- Do not alter a test merely to make incorrect application behavior appear correct. Update the data contract first if a genuine requirement change is needed.

## 7. Documentation Rules

- Documentation must match implemented behavior, not intended behavior.
- Label planned, implemented, and verified features accurately.
- Add a data-dictionary entry for persisted schema changes.
- Add or update validation rules when accepted/rejected data behavior changes.
- Add architecture and decision records when adding a new component or changing a substantial design choice.
- Keep setup commands tested on the supported environment.
- Keep known limitations visible; do not hide a limitation to make the project look more advanced.

## 8. Final Response Format After a Phase

Return the following headings:

1. **Phase and outcome** — complete / partially complete / blocked.
2. **Implemented** — concise list of verified changes.
3. **Verification** — exact commands and pass/fail/skip results.
4. **GitHub** — branch, commit SHA, push status, and URL if available.
5. **Known issues** — remaining issues or none found in tested scope.
6. **Next phase** — propose the next phase, but do not start it within the same handoff.

A phase is not complete if its code is implemented but required verification or the requested GitHub handoff is still outstanding.
