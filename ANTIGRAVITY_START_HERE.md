# Start BankFlow in Antigravity

This file is the launch guide for the developer and Antigravity. BankFlow is at the **planning stage**. Do not generate the full application in one prompt.

## Before starting

1. Open the complete local `BankFlow` folder in Antigravity.
2. Confirm `plan.md` is present at the repository root.
3. Confirm the supporting files listed below are present.
4. Open a terminal and inspect `git status`, the active branch, and `git remote -v`.
5. Ensure the intended remote is `https://github.com/GouravSharma26/BankFlow.git`. Do not overwrite an unrelated remote or existing Git history.
6. Commit and push the documentation baseline if it is not already on GitHub. Follow `REVIEW_WORKFLOW.md`.

## Required project documents

- `AGENTS.md` — rules Antigravity must follow while coding.
- `plan.md` — full project plan and canonical scope.
- `DEVELOPMENT_CHECKLIST.md` — the only authoritative phase checklist.
- `REVIEW_WORKFLOW.md` — required commit/push/review handoff.
- `PHASE_LOG.md` — verified implementation evidence and reviewer findings.
- `HUMAN_SETUP.md` — environment and safety setup.
- `docs/architecture.md` — system boundaries and data flow.
- `docs/data_contract.md` — source data and validation semantics.
- `docs/design_decisions.md` — technology choices and decision history.
- `docs/testing_strategy.md` — tests and evidence requirements.
- `docs/data_dictionary.md` — actual database schema documentation, to be filled in as schema is implemented.
- `docs/data_quality_rules.md` — stable validation rule catalogue, to be finalized during validation phase.
- `docs/metric_definitions.md` — definitions for SQL reports and dashboard values.

## First prompt to give Antigravity

Copy this prompt after opening the repository folder:

> You are the implementation engineer for BankFlow. Before changing anything, read `AGENTS.md`, `plan.md`, `DEVELOPMENT_CHECKLIST.md`, `REVIEW_WORKFLOW.md`, `PHASE_LOG.md`, `HUMAN_SETUP.md`, and every Markdown file under `docs/`. The project is currently at planning stage; do not assume any application code has been implemented.
>
> First inspect the actual repository: list files, inspect `git status`, current branch, latest commit, and `git remote -v`. Preserve existing work. Confirm whether the GitHub repository has a baseline commit and whether the expected remote is configured. Do not reinitialize Git if history already exists. If GitHub authentication prevents a push, report the exact blocker and do not claim success.
>
> Then execute **only the first unchecked phase** in `DEVELOPMENT_CHECKLIST.md`. Do not build the entire project in one pass or start later phases. Before implementation, summarize the phase objective, files expected to change, and exit criteria. Follow `plan.md` as the canonical scope. Use synthetic data only, preserve raw/staging values needed for diagnosis, use `Decimal`/PostgreSQL `NUMERIC` for monetary values, define currency and transaction-status semantics, and design replay-safe database loading. Do not add optional frameworks or cloud services just to make the stack look advanced.
>
> Implement the smallest testable increment, run all applicable checks, inspect the diff for secrets/generated files/unrelated changes, update the checklist and phase log truthfully, and follow `REVIEW_WORKFLOW.md` to commit and push the completed phase. Never force-push or bypass repository protections. Report exact test commands/results, branch, commit SHA, actual push status, remaining issues, and the next phase. Do not start the next phase before handoff.

## After each phase

1. Let Antigravity complete verification, commit, and push according to `AGENTS.md`.
2. Confirm the branch/commit is visible on GitHub.
3. Return to the ChatGPT conversation and request a code review using `REVIEW_WORKFLOW.md`.
4. Fix blocking/high-priority findings and push the fix commit.
5. Start the next phase only after the current phase's exit criteria are satisfied.

## Important limitation

A local commit does not mean the code was pushed. An agent must verify the push output and provide the real branch/commit URL. ChatGPT reviews the latest visible repository state when asked in the conversation; it is not silently monitoring GitHub in the background.
