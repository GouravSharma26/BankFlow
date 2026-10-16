# BankFlow — Testing Strategy

> Testing is part of feature completion, not a final cleanup task. Match tests to the risk they are meant to control and use synthetic fixtures with known expected results.

## 1. Test Layers

### 1.1 Unit Tests

Fast tests that do not need PostgreSQL. Target pure functions and deterministic behavior:

- CSV field normalization and allowed-value mappings.
- Amount parsing using decimal semantics.
- Timestamp parsing and timezone normalization.
- Required-field and domain validation.
- Each stable data-quality rule code.
- Transformation functions and derived date attributes.
- Synthetic generator reproducibility with a fixed seed.
- Reconciliation arithmetic and edge cases.
- CLI argument validation where appropriate.

Unit tests should not depend on network access, secret keys, real input data, or external dashboards.

### 1.2 PostgreSQL Integration Tests

Run against a dedicated, clearly identified test database. Target behavior that Python mocks cannot verify:

- Schema initialization and constraints.
- Foreign-key and unique-key enforcement.
- Dimension/fact loading and reference resolution.
- Atomic transaction rollback on induced failure.
- Idempotent replay of a file/event.
- Batch status and counts persisted accurately.
- Quality issue rows linked to source batch/row.
- SQL reporting views and aggregations.

Never run destructive test fixtures against the developer's normal database. Validate the target database before cleanup or test setup.

### 1.3 End-to-End Tests

Run the key workflow against a temporary/dedicated test database:

1. Generate a small fixed-seed synthetic dataset.
2. Initialize schema.
3. Run the ETL.
4. Query staging, quality issues, dimensions, facts, and monitoring rows.
5. Compare output to expected counts/metrics.
6. Rerun the same file and confirm no duplicate fact rows.
7. Verify batch outcome and reconciliation summary.

Use small datasets in CI. Larger benchmarks should be manual or separately marked.

### 1.4 Failure-Injection Tests

At minimum, test:

- Missing required source header.
- Empty source file.
- Malformed amount and timestamp.
- Missing transaction ID.
- Duplicate event ID inside one file.
- Replay of an already-loaded input.
- Unknown account reference.
- Unsupported domain value.
- Failure during warehouse loading to verify rollback.
- Database unavailable at startup or mid-run where feasible.
- Late-arriving event, according to the documented MVP policy.

Every injected defect must have a known expected outcome. Avoid tests that merely assert “an exception happened” if the contract requires a particular issue code or batch state.

## 2. Reconciliation Assertions

Check accounting identities appropriate to the implemented workflow. At a minimum:

- Every staged row has a documented disposition: accepted, rejected, intentionally skipped, or explicitly unprocessed because of a file-level failure.
- Every rejected row generates the required quality record(s).
- Every accepted event maps to a documented insert/update/skip outcome.
- Fact counts and accepted source event identities agree under the deduplication policy.
- Aggregates compared across layers use the same filters, status semantics, and currency grouping.
- Dashboard metrics are equal to the equivalent reporting SQL values for selected fixture cases.

Do not claim reconciliation success by comparing totals with different semantics.

## 3. Monetary and Time Tests

- Use decimal test values that expose binary floating-point mistakes (for example, repeated decimal fractions) while asserting the correct expected sum.
- Test timezone offsets and dates near midnight to ensure the reporting date is derived according to a documented timezone rule.
- Verify that currency values do not get unintentionally merged in aggregates.
- Confirm that reversals and failed/pending statuses follow documented reporting definitions.

## 4. Idempotency Tests

Test all relevant cases:

1. First run inserts the expected accepted events.
2. Second run of the exact same file creates no duplicate facts.
3. Same event ID with conflicting payload follows the documented immutable-event policy (e.g. flag rather than silently overwrite).
4. Concurrent/retried execution is protected by database uniqueness even if two application processes attempt the same event.
5. Insert/skip/error counts remain internally consistent.

Database constraints are required; an in-memory set alone is not sufficient.

## 5. CI Requirements

GitHub Actions should eventually:

- Install the selected supported Python version and project dependencies.
- Run formatting/lint checks only if those tools are configured and documented.
- Run unit tests.
- Start or connect to a dedicated PostgreSQL service for integration tests if such tests are in the CI scope.
- Set an explicit test database URL in CI secrets or job environment as appropriate; avoid production/developer credentials.
- Fail the workflow when required tests fail.
- Avoid depending on Power BI Desktop or interactive dashboard steps in the base CI job.

If PostgreSQL integration tests are temporarily excluded from a lightweight workflow, state that explicitly and keep a separate reproducible command for them. Do not report an incomplete CI suite as full test coverage.

## 6. Test Evidence in Phase Handoffs

Every phase report should include:

- Exact command(s) executed.
- Pass/fail/skip results and counts when available.
- Environment details if relevant to a failure.
- Tests added for new behavior.
- Known gaps and what remains to be tested.

Do not write “all tests pass” unless the full required test suite was actually executed and succeeded.
