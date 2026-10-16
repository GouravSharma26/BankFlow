# BankFlow — Phase Push and Review Workflow

This workflow implements the user's requirement: after every development phase, push the work to GitHub and obtain a review before advancing.

Repository: <https://github.com/GouravSharma26/BankFlow>
Remote URL: `https://github.com/GouravSharma26/BankFlow.git`

## 1. One-Time Baseline

Before implementation starts:

1. Confirm the local folder is the intended BankFlow repository.
2. Inspect `git status`, `git branch --show-current`, and `git remote -v`.
3. Verify the root includes `plan.md`, `AGENTS.md`, `README.md`, `DEVELOPMENT_CHECKLIST.md`, and `PHASE_LOG.md` plus the `docs/` references.
4. If this is a newly initialized repository, create the first baseline commit and push it to `main` only after checking the complete staged diff.
5. If history already exists, do not reinitialize Git or overwrite the existing branch. Commit the new documents normally.
6. Confirm the baseline appears in GitHub before coding begins.

Do not force-push. If a repository has been initialized remotely by another process, fetch and reconcile histories rather than overwriting one history with another.

## 2. At the Start of Every Phase

The coding agent should:

- Read `AGENTS.md` and the relevant phase in `DEVELOPMENT_CHECKLIST.md`.
- Read the related section in `plan.md` and applicable docs.
- Confirm the current branch and clean/known working-tree state.
- State the phase objective, work scope, and exit criteria before editing.
- Never mix unrelated refactors or the next phase into the current phase.

## 3. Before Commit

The agent must run what applies to the phase and inspect output. At minimum:

```bash
git status --short
git diff --check
git diff --stat
git diff
```

Also:

- Run the relevant tests and report the actual results.
- Check for `.env`, tokens, credentials, real personal/financial data, database dumps, generated data, caches, and virtual environments.
- Confirm docs and `DEVELOPMENT_CHECKLIST.md` match the implemented state.
- Append a dated phase entry to `PHASE_LOG.md`.
- Stage only files that belong to the phase and inspect the staged diff before committing.

## 4. Branch and Commit Convention

For implementation phases, prefer a branch for the phase, e.g.:

```bash
git switch -c phase/1-foundation
```

Use a focused conventional commit such as:

```bash
git add <specific-files>
git diff --cached --check
git diff --cached
git commit -m "feat(foundation): add generator and staging schema"
```

Use conventional prefixes where useful: `docs:`, `feat:`, `fix:`, `test:`, `refactor:`, `chore:`. Do not use `git add .` blindly; generated files or local settings may be included accidentally.

If continuing on a phase branch, verify that it was created from the expected base and is not carrying unrelated work.

## 5. Push and Confirm

After the commit and successful phase verification:

```bash
git push -u origin phase/1-foundation
```

Use the actual phase branch name. A one-time documentation baseline may be pushed to `main` if no history exists; implementation phase branches should be pushed without force. If the user's repository workflow intentionally uses `main` directly, follow the established repository convention after confirming it is safe.

After pushing:

1. Confirm the push command succeeded.
2. Record branch and commit SHA in `PHASE_LOG.md`.
3. Provide the GitHub branch or commit URL when available.
4. Do not report a push succeeded based solely on a local commit.
5. If authentication or permissions fail, provide the exact error and let the user resolve it. Do not expose or request tokens in chat.

## 6. Review by ChatGPT

When a phase is pushed, the user should return to the ChatGPT conversation and say, for example:

> BankFlow Phase 1 is pushed. Review the latest code at https://github.com/GouravSharma26/BankFlow/tree/phase/1-foundation and check commit `<SHA>`. Compare it against `plan.md`, `AGENTS.md`, and the Phase 1 acceptance criteria. Find bugs, missing requirements, security risks, data correctness issues, test gaps, and documentation drift. Give prioritized findings with file/line references and required fixes. Do not assume a feature works only because README says it does.

If changes are pushed to `main`, provide the main URL and exact commit SHA. For reliable review, provide the branch/commit URL because repository default branches and visible content can change between review sessions.

Review priorities:

1. Correctness and data integrity
2. Security/privacy and unsafe database operations
3. Idempotency, transaction boundaries, and failure handling
4. Validation coverage, reconciliation, and SQL semantics
5. Test quality and reproducibility
6. Plan/checklist/documentation consistency
7. Maintainability and scope creep

The review should distinguish confirmed defects from risks or questions that need runtime evidence. Findings should identify the affected file and line(s) when possible, state impact, and give a concrete correction. Do not rewrite large areas unnecessarily.

## 7. Feedback Loop

- Fix blocking/high-priority findings before advancing.
- Record review findings and their disposition in `PHASE_LOG.md`.
- Push fixes to the same phase branch with a separate focused commit.
- Ask for a follow-up review of the new commit when the fixes are ready.
- Mark the phase `VERIFIED` only after all exit criteria and required fixes are satisfied.
- Do not begin the next phase while a correctness or security blocker is unresolved.

## 8. Limits of This Workflow

This is a deliberate handoff workflow, not continuous background monitoring. ChatGPT reviews the repository when asked in the conversation; it does not silently watch GitHub or guarantee automatic detection of new commits. The GitHub push itself is performed from the user's development environment/Antigravity and its configured Git credentials.
