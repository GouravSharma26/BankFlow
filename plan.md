# BankFlow — Banking Transaction ETL & Analytics Warehouse

> **Project execution plan**  
> Version: 1.0  
> Status: Planned  
> Primary audience: Student developer, reviewers, and interviewers  
> Target: A reproducible, tested, portfolio-grade data engineering project using synthetic banking data only

---

## 1. Project Summary

BankFlow is a small banking analytics data platform that demonstrates how raw transaction data can be ingested, validated, cleaned, transformed, loaded into a dimensional PostgreSQL warehouse, and used for reliable reporting.

The project is designed to demonstrate practical skills relevant to entry-level Data Engineer, Data Analyst, and Software Application Analyst roles:

- Python programming and structured data processing
- SQL querying, aggregation, joins, constraints, and query analysis
- Relational modelling and dimensional data warehousing
- ETL design, batch tracking, validation, and reconciliation
- Idempotent processing and transaction-safe loading
- Automated testing, version control, CI, documentation, and reproducible setup
- Dashboard/report development using clearly defined metrics

**This is an educational simulation, not a banking system.** It will use generated or clearly synthetic records only. It will not connect to real bank systems, process real customer records, initiate payments, or produce actual financial decisions.

### 1.1 Problem Statement

Transaction data arriving from different source files may contain duplicates, missing identifiers, malformed timestamps, invalid references, inconsistent category labels, and other quality problems. Analysts should not have to guess whether reported figures are complete or trustworthy.

BankFlow will establish a repeatable path from raw input to validated analytical outputs. Every batch should have a traceable outcome, invalid rows should be accounted for, and rerunning a batch must not create duplicate warehouse facts.

### 1.2 Main Objective

Build an end-to-end batch ETL and analytics workflow that turns synthetic source records into a queryable warehouse with documented data-quality rules, reconciliation checks, automated tests, and a dashboard.

### 1.3 Success Definition

The project is ready for a portfolio demonstration when a reviewer can clone the repository, configure the environment, create the database, generate sample input, run the ETL, query the warehouse, inspect rejected records, run tests, and reproduce dashboard metrics using the repository documentation.

---

## 2. Goals, Non-Goals, and Scope

### 2.1 In Scope — Minimum Viable Product (MVP)

1. Generate synthetic customers, accounts, branches, and transaction events.
2. Include configurable clean records and deliberate test defects.
3. Ingest CSV files into a raw/staging layer while capturing source and batch metadata.
4. Validate source structure, required fields, identifiers, timestamps, transaction types, amounts, currency, and references.
5. Preserve invalid rows and record structured rejection reasons.
6. Transform accepted rows into consistent warehouse-ready records.
7. Load dimensions and transaction facts into PostgreSQL.
8. Make loads idempotent using a documented business key and database constraints.
9. Track batch state, row counts, errors, and reconciliation results.
10. Provide SQL examples and reporting views for transaction volume, value, branch activity, transaction types, and data quality.
11. Build a simple dashboard with an overview, transaction analysis, and pipeline/data-quality views.
12. Add unit tests, PostgreSQL integration tests, CI, setup instructions, architecture notes, and a data dictionary.

### 2.2 Out of Scope for MVP

- Connecting to a bank API or production payment system
- Real customer/account data or personal data
- Initiating, approving, or settling financial transactions
- Fraud detection that claims to identify real financial crime
- Real-time streaming, Kafka, or a distributed event-processing platform
- A large-scale cloud deployment
- Apache Airflow before the core batch pipeline is stable
- Oracle/PL/SQL implementation unless deliberately chosen as a later extension
- Regulatory or accounting certification

### 2.3 Optional Extensions — Only After MVP

- Incremental extraction using watermarks and late-arriving event handling
- Slowly Changing Dimension Type 2 for selected historical attributes
- Docker Compose-based one-command development environment
- Airflow or another orchestrator for dependency management and retries
- Oracle/PL/SQL version of selected transformations
- Query-plan comparisons and documented performance benchmarks
- Great Expectations or a similarly structured data-quality framework
- A second reporting tool if there is a concrete reason to support it

**Scope rule:** Do not add an extension while a core acceptance criterion is failing.

---

## 3. Target Users and Use Cases

### 3.1 Intended Users

- A data analyst who needs consistent transaction reports
- A data engineer who needs to monitor ingestion and quality
- A developer who needs to reproduce a pipeline failure
- A recruiter or interviewer evaluating practical database and ETL understanding

### 3.2 Demonstration Use Cases

1. Generate a new dataset and ingest it into staging.
2. Find source records that violate validation rules.
3. Load validated records into a dimensional warehouse.
4. Re-run an already processed input and prove that facts are not duplicated.
5. Calculate daily transaction counts and values using SQL.
6. Reconcile source, accepted, rejected, inserted, and updated counts.
7. Identify why a batch failed and view its error summary.
8. Compare dashboard totals with direct SQL results.

---

## 4. Technology Decisions

| Area | MVP choice | Reason | Alternatives / later consideration |
|---|---|---|---|
| Language | Python 3.12+ | Widely used for ETL and straightforward to test | Use a supported version available in the development environment |
| Database | PostgreSQL | Strong relational constraints, SQL, transactions, and indexing | Oracle only as an intentional extension |
| Data processing | Python standard library plus Pandas where useful | Simple parsing and transformations without overengineering | Polars for a demonstrated performance need |
| Database access | SQLAlchemy or psycopg | Clear database access layer and parameterized SQL | Choose one primary access method initially |
| Data format | CSV for source files | Easy to inspect and generate | Parquet for a later analytical-format extension |
| Testing | pytest | Unit and integration test support | None required for MVP |
| Version control | Git and GitHub | Reviewable change history and collaboration practice | None |
| CI | GitHub Actions | Automated test execution on changes | None required for MVP |
| Dashboard | Power BI or Metabase | Clear reporting from SQL outputs | Choose one to keep scope manageable |
| Scheduling | Manual CLI first; cron later | Debuggable before scheduling complexity | Airflow after MVP |
| Packaging | `pyproject.toml` | Project metadata and dependency configuration | Use a lock file if a package manager is selected |
| Containerization | Optional Docker Compose | Reproducible local PostgreSQL/application setup | Add after local setup works reliably |

### 4.1 General Engineering Rules

- Keep dependencies minimal and explain why each dependency exists.
- Do not hardcode credentials or commit `.env` files.
- Use parameterized SQL; do not build SQL by concatenating untrusted values.
- Use `Decimal`/PostgreSQL `NUMERIC` for monetary amounts, not binary floating-point arithmetic.
- Use explicit time-zone handling and document the reporting timezone.
- Separate orchestration, extraction, validation, transformation, loading, and reporting logic.
- Prefer transparent SQL and small Python functions over unnecessary abstractions.
- Record actual benchmark numbers only after measurement.

---

## 5. High-Level Architecture

```text
Synthetic Data Generator
        |
        v
Raw CSV Files (immutable source inputs)
        |
        v
Extract + Batch Registration
        |
        v
PostgreSQL Staging Layer -----> Batch / Pipeline Run Log
        |                                  |
        v                                  v
Validate + Normalize              Error and Quality Records
        |
        +---- invalid rows ------> Quarantine / Quality Issue Table
        |
        v
Transform + Dimension Lookup
        |
        v
PostgreSQL Warehouse
  - Dimensions
  - Fact Transactions
        |
        v
Reporting Views + SQL Queries
        |
        v
Dashboard / Exported Reports
```

### 5.1 Data Layers

1. **Raw input:** Source CSVs generated by the synthetic data generator. Preserve the source files unchanged for traceability.
2. **Staging:** Raw source values and ingestion metadata. Staging retains records that may later be rejected.
3. **Quality/quarantine:** Structured issue rows with batch ID, source row reference, rule code, and explanation.
4. **Warehouse:** Conformed dimensions and a transaction fact table for analytical queries.
5. **Reporting:** SQL views and dashboard queries with documented business definitions.
6. **Operational metadata:** Batch runs, processing counts, status, durations, and error summaries.

### 5.2 Component Boundaries

- `generator`: makes synthetic files and controllable defect cases.
- `extraction`: reads files, validates file-level structure, and registers batches.
- `validation`: applies row-level and reference rules and produces issues.
- `transformation`: normalizes values and derives warehouse fields.
- `loading`: loads dimensions/facts safely and idempotently.
- `analytics`: provides query definitions and report calculations.
- `monitoring`: exposes batch metadata, counts, errors, and run summaries.
- `etl.py`: coordinates the phases and returns a clear exit status.

---

## 6. Data Model and Database Design

Use separate schemas or consistently named tables for staging, warehouse, and reporting. For the MVP, schemas such as `staging`, `warehouse`, and `reporting` make responsibilities clear. A `public` schema can hold database extensions only if needed.

### 6.1 Synthetic Source Entities

#### Customers

Suggested fields:

- `customer_id`: synthetic business identifier
- `customer_segment`: e.g. retail, small business, or premium segment
- `created_date`: synthetic creation date
- `customer_status`: active or inactive

Do not generate real names, phone numbers, addresses, government IDs, or other realistic personal details unless strictly necessary. Prefer opaque synthetic identifiers.

#### Accounts

Suggested fields:

- `account_id`: synthetic account identifier
- `customer_id`: customer reference
- `branch_id`: branch reference
- `account_type`: current, savings, or another documented simulated type
- `account_status`: open, closed, or restricted in the simulated domain
- `opened_date`: synthetic date
- `currency`: ISO-style currency code for supported test currencies

#### Branches

Suggested fields:

- `branch_id`: branch identifier
- `branch_name`: synthetic branch name
- `region`: synthetic region code

#### Transactions

Suggested fields:

- `transaction_id`: source business identifier
- `account_id`: source account identifier
- `transaction_type`: deposit, withdrawal, transfer, payment, fee, reversal, or another documented type
- `amount`: decimal source amount
- `currency`: currency code
- `transaction_timestamp`: source event timestamp
- `status`: completed, pending, failed, or reversed as explicitly defined
- `channel`: branch, ATM, online, mobile, or another defined simulated channel
- `counterparty_account_id`: optional reference for transfer simulations, if included
- `source_system`: synthetic source name

Keep the distinction between a transaction event and an account balance explicit. The MVP reports event counts and event values; it should not imply that summing all event amounts computes a current account balance.

### 6.2 Staging Tables

#### `staging.stg_transactions`

Recommended columns:

- `source_row_id` — generated primary key for an ingested row
- `transaction_id` — source business identifier, nullable if source value is missing
- `account_id` — original account reference
- `transaction_type` — original transaction type
- `amount_raw` — source text or a suitable staging representation that does not prevent malformed rows from being captured
- `currency` — original currency value
- `transaction_timestamp_raw` — original timestamp string
- `status` — original status value
- `channel` — original channel value
- `source_file` — source filename or stable source identifier
- `batch_id` — ETL batch identifier
- `source_row_number` — position in the source file when available
- `raw_payload` — optional JSONB snapshot for full row preservation
- `ingested_at` — ingestion timestamp

Staging data should not depend on successful business validation. Ensure malformed amounts or timestamps can still be recorded for quality reporting instead of causing silent row loss during parsing.

#### `staging.stg_accounts`, `staging.stg_customers`, `staging.stg_branches`

Use corresponding staging tables for source entities where needed. These may be loaded before transaction batches so references can be resolved, or their loading order may be handled explicitly by the pipeline.

### 6.3 Pipeline Metadata Tables

#### `monitoring.etl_batch_runs`

Suggested fields:

- `batch_id` — primary key, UUID or stable generated identifier
- `source_name` or `source_file`
- `started_at`
- `completed_at`
- `status` — pending, running, succeeded, succeeded_with_rejections, failed
- `records_extracted`
- `records_staged`
- `records_valid`
- `records_rejected`
- `records_inserted`
- `records_updated`
- `records_skipped` — e.g. known replay or duplicate according to policy
- `reconciliation_status`
- `error_summary`
- `created_at`

Counts should have one documented meaning and must not be double-counted. For example, `records_extracted` is the number of source rows read, while `records_staged` is the number successfully captured in staging. If file-level errors prevent row extraction, record that condition explicitly.

#### `monitoring.data_quality_issues`

Suggested fields:

- `issue_id` — primary key
- `batch_id` — batch reference
- `source_row_id` — staging row reference where possible
- `source_file`
- `source_row_number`
- `rule_code`
- `severity` — error, warning, or informational
- `reason`
- `detected_at`
- `resolution_status` — open, resolved, or ignored with rationale if resolution tracking is implemented

Avoid storing sensitive information in issue descriptions. Include enough information to diagnose the row without copying unnecessary payloads into logs.

### 6.4 Warehouse Dimensions

#### `warehouse.dim_customer`

- `customer_key` — surrogate primary key
- `customer_id` — source business key, unique according to the customer source contract
- `customer_segment`
- `customer_status`
- Optional `valid_from`, `valid_to`, `is_current` if a historical dimension extension is implemented

#### `warehouse.dim_account`

- `account_key` — surrogate primary key
- `account_id` — source account business key
- `customer_key` — customer dimension foreign key
- `branch_key` — branch dimension foreign key
- `account_type`
- `account_status`
- `currency`

#### `warehouse.dim_branch`

- `branch_key` — surrogate primary key
- `branch_id` — source business key
- `branch_name`
- `region`

#### `warehouse.dim_date`

- `date_key` — integer representation of the calendar date, such as `YYYYMMDD`
- `full_date`
- `day_of_month`
- `day_of_week`
- `week_of_year`
- `month_number`
- `month_name`
- `quarter_number`
- `year_number`
- `is_weekend`

Populate the date dimension for the project's supported date range. Define how dates are derived when transaction timestamps are converted into the reporting timezone.

#### `warehouse.dim_transaction_type`

- `type_key` — surrogate primary key
- `transaction_type_code` — unique business code
- `transaction_type_name`
- `transaction_family` — e.g. credit, debit, transfer, adjustment

Do not assume every transaction type can be classified as a simple credit or debit without defining its semantics.

### 6.5 Transaction Fact Table

#### `warehouse.fact_transactions`

One row represents one accepted transaction event under the source system's documented event identity rules.

Suggested fields:

- `transaction_key` — warehouse primary key
- `transaction_id` — source business identifier
- `source_system` — source identity
- `account_key` — dimension foreign key
- `customer_key` — optional direct customer dimension key if justified by reporting needs; otherwise derive it through account
- `branch_key` — branch dimension key
- `date_key` — transaction event date key
- `type_key` — transaction type dimension key
- `amount` — `NUMERIC`, with documented precision and scale
- `currency` — currency code
- `status` — transaction status
- `channel` — channel attribute or a channel dimension if later required
- `source_batch_id` — lineage back to ETL batch
- `source_row_id` — lineage back to staging record
- `loaded_at` — warehouse load timestamp

Create a unique constraint for the chosen stable event identity, such as (`source_system`, `transaction_id`) if the source contract guarantees that this combination uniquely identifies an event. If transaction IDs can be reused or represent mutable records, document the alternative identity/versioning strategy rather than assuming global uniqueness.

### 6.6 Schema Integrity Rules

- Use primary and foreign keys for relationships.
- Add uniqueness constraints for business identifiers according to the source contract.
- Add `CHECK` constraints for clearly defined enums and amount requirements where suitable.
- Use `NUMERIC(p,s)` or equivalent decimal semantics for money.
- Index columns used frequently for joins, uniqueness, and common report filters.
- Avoid adding indexes without a usage reason; document any index whose impact is measured.
- Keep business identifiers distinct from surrogate warehouse keys.
- Define how unknown/missing dimension keys are represented. Do not fabricate customer or account attributes.

---

## 7. Data Generation Plan

### 7.1 Dataset Size

Start small and increase gradually:

- Smoke-test dataset: 100–500 transactions
- Development dataset: 5,000–10,000 transactions
- Benchmark dataset: 50,000–100,000 transactions only after correctness is established

These are planning sizes, not required throughput claims. Larger sizes are optional and should not block completion.

### 7.2 Generator Requirements

- Use a fixed seed option for repeatable datasets.
- Generate customers and accounts before transactions.
- Make account and branch references internally consistent for the clean portion of data.
- Include configurable date ranges and volume.
- Use deterministic IDs for reproducible fixtures where appropriate.
- Allow the user to choose the defect percentage or particular defect scenarios.
- Clearly label every generated dataset as synthetic.

### 7.3 Injected Defect Scenarios

Include separate scenarios so each validation rule can be demonstrated:

1. Missing transaction ID
2. Duplicate event ID
3. Missing account ID
4. Unknown account reference
5. Unsupported transaction type
6. Missing currency
7. Invalid timestamp text
8. Missing amount
9. Non-numeric amount
10. Amount outside the allowed rule for the chosen transaction type
11. Unsupported status
12. Duplicate file/replay of previously loaded data
13. Header mismatch or required column missing
14. Empty file
15. Late-arriving transaction from a prior event date

Do not inject a defect and then silently remove it. Every test fixture should have an expected validation result.

### 7.4 Data Contract

Document for every source field:

- Required or optional status
- Accepted format and type
- Allowed values/range
- Null handling
- Normalization behavior
- Rejection or warning behavior
- Target field mapping

The ETL pipeline should fail fast on structural file-contract failures, while handling row-level defects according to documented reject/quarantine policy.

---

## 8. ETL Execution Design

### 8.1 Proposed Command-Line Interface

The exact syntax can change, but commands should be explicit and discoverable. Possible interface:

```bash
# Create sample source files
python -m bankflow generate --transactions 10000 --seed 42 --output data/raw

# Initialize the schema
python -m bankflow db init

# Run a batch
python -m bankflow etl run --input data/raw/transactions.csv

# Inspect a batch
python -m bankflow etl status --batch-id <BATCH_ID>

# Run validation/report checks
python -m bankflow quality report --batch-id <BATCH_ID>

# Run analytics examples
python -m bankflow analytics daily-transactions
```

These are interface proposals. Implement a smaller CLI first if that helps avoid overengineering.

### 8.2 Pipeline State Machine

Recommended batch states:

```text
PENDING -> RUNNING -> SUCCEEDED
                    -> SUCCEEDED_WITH_REJECTIONS
                    -> FAILED
```

Rules:

- A batch must be created and marked running before work begins.
- Successful completion should record end time, counts, and reconciliation status.
- Row-level rejects may produce `SUCCEEDED_WITH_REJECTIONS` if the configured policy allows the batch to continue.
- Structural or infrastructure failures should mark the batch failed and preserve a useful error summary.
- Do not mark a batch successful before warehouse changes commit.
- Repeated requests to run the same input need a documented policy: return an existing result, create a new attempt linked to the same source fingerprint, or process safely via idempotent constraints.

### 8.3 Extract Stage

1. Discover the input path and verify it exists.
2. Compute or record a file fingerprint (e.g. checksum) where helpful for replay detection.
3. Check required headers and encoding.
4. Read in configurable chunks for larger datasets.
5. Preserve source filename and row number.
6. Insert raw values and batch metadata into staging.
7. Record extraction counts and file-level failures.

If parsing a row fails, preserve enough of the original content to explain the issue. If a file cannot be read at all, store a batch-level failure rather than pretending it contained zero valid transactions.

### 8.4 Validation Stage

Suggested rule categories:

- **File-level:** required headers, unsupported file format, invalid encoding
- **Schema-level:** required fields missing from an individual record
- **Syntax-level:** invalid numeric amount, malformed timestamp
- **Domain-level:** unsupported type, status, channel, or currency
- **Referential:** unknown account, customer, or branch
- **Uniqueness:** duplicate source event key
- **Business-rule:** amount or transition inconsistent with the documented simulated data contract

Each validation rule must have a stable `rule_code`, an explanation, and a deterministic outcome. A record can violate more than one rule; document whether the pipeline records every issue or stops at the first fatal issue per row.

### 8.5 Transform Stage

- Strip leading/trailing whitespace from categorical values.
- Standardize category labels using explicit mappings.
- Parse decimal amounts exactly.
- Parse timestamps with known source formats; do not guess silently if ambiguous.
- Normalize timestamps and record reporting-date semantics.
- Resolve dimension keys after dimensions have been loaded.
- Preserve original transaction identifiers for lineage.
- Treat reversals and corrections according to documented event semantics.
- Avoid aggregating individual transactions during the fact-load stage; aggregate in reporting queries unless a clear performance requirement justifies a summary table.

### 8.6 Load Stage

- Load/refresh required dimensions first.
- Load facts only after references can be resolved.
- Use a transaction for logically related warehouse changes.
- Use bulk operations for reasonable volumes if they are simpler and safe.
- Enforce idempotency in the database, not only in application memory.
- Track inserted, updated, rejected, and skipped counts separately.
- Roll back the appropriate transaction scope on failure.
- Preserve enough batch/staging references to trace a fact row to its source.

### 8.7 Idempotency Strategy

Definition: processing the same accepted source event again should not create another fact record.

Required controls:

1. Define a stable source event key.
2. Add a matching uniqueness constraint in the warehouse.
3. Use safe insert/upsert behavior.
4. Distinguish a replay from a legitimate correction or updated source event.
5. Record insert/update/skip counts.
6. Test rerunning the same file and batch.

For the MVP, choose one simple source contract: transaction event identifiers are immutable and unique per source system. If you later model mutable event updates, include a source modification timestamp or version and define how corrections are applied.

### 8.8 Reconciliation

At the end of each run, produce a machine-readable summary and a human-readable log.

At minimum, check:

- Extracted rows are accounted for as staged or explicitly unprocessed due to a file-level error.
- Staged rows are accounted for as valid, rejected, or intentionally skipped.
- Valid records have a documented outcome: inserted, updated, or skipped due to an already-known event.
- Invalid rows have corresponding quality records according to the validation policy.
- Warehouse facts can be traced to source/batch metadata.
- Defined value/count totals match at comparable stages.

Do not compare totals that have different semantics. For example, source totals including failed transactions cannot be expected to equal a completed-only dashboard metric.

---

## 9. Data Quality Policy

### 9.1 Severity Levels

- **ERROR:** Record must not enter the warehouse as a valid fact under the current rules.
- **WARNING:** Record may load, but it has a condition worth examining.
- **INFO:** Expected operational event, such as a duplicate replay safely skipped.

### 9.2 Example Rule Catalogue

| Rule code | Condition | Severity | Expected response |
|---|---|---|---|
| `FILE_REQUIRED_COLUMN_MISSING` | A required CSV header is absent | Error / batch-level | Fail the file before row load |
| `TXN_ID_MISSING` | Transaction ID absent | Error | Quarantine the row |
| `TXN_ID_DUPLICATE` | Duplicate source event identity | Policy-dependent | Quarantine, deduplicate, or classify as replay per contract |
| `AMOUNT_PARSE_ERROR` | Amount cannot be parsed | Error | Preserve source value; reject row |
| `AMOUNT_RULE_VIOLATION` | Amount violates defined type-specific rule | Error or warning | Reject or flag according to specification |
| `TIMESTAMP_PARSE_ERROR` | Timestamp cannot be parsed | Error | Reject row |
| `ACCOUNT_NOT_FOUND` | Account reference cannot be resolved | Error | Reject/quarantine unless a documented late-arrival path applies |
| `TYPE_UNSUPPORTED` | Transaction type is unmapped | Error | Reject row; update mapping intentionally |
| `CURRENCY_UNSUPPORTED` | Currency is outside configured set | Error | Reject or quarantine |
| `SOURCE_REPLAY_SKIPPED` | Same event has already been loaded | Info | Skip safely and record disposition |
| `LOW_DAILY_VOLUME` | Volume is unusually low against a configured simple threshold | Warning | Report for review; do not automatically alter data |

### 9.3 Rejection Handling

- Rejecting a row must create a quality issue with a stable rule code and reason.
- Avoid logging secrets or unnecessary source payload content.
- Preserve access to the original source data for debugging.
- Define whether one row can have several issue entries.
- Distinguish row-level issues from infrastructure or file-level failures.
- Do not silently discard malformed rows.

---

## 10. Analytics and Business Metric Definitions

Every report metric needs a written definition. The dashboard and SQL should use the same logic.

### 10.1 Core Metrics

1. **Ingested row count:** number of source rows discovered/read by a batch, with a documented treatment of unreadable files.
2. **Accepted row count:** number of source rows that passed the defined validation criteria for warehouse loading.
3. **Rejected row count:** number of source rows rejected due to configured validation rules. This is a row count, not necessarily the number of issue records.
4. **Inserted fact count:** new fact rows committed by the batch.
5. **Skipped/replay count:** valid source events that were not reinserted because they were already present under the idempotency contract.
6. **Completed transaction count:** number of fact events whose status meets the defined completed-status filter.
7. **Transaction event value:** sum of amounts for the explicitly selected types, statuses, and currencies.
8. **Branch activity:** event counts and values grouped by branch.
9. **Data-quality issue count:** number of issues by rule, severity, and batch.
10. **Batch duration:** elapsed time from batch start to completion, using consistent timestamp semantics.

### 10.2 Monetary Aggregation Rules

- Do not sum amounts across currencies unless they have been normalized using an explicitly documented conversion rate and effective date.
- Clearly label a metric as event value, not account balance, bank revenue, or profit.
- Decide whether pending, failed, completed, and reversed events are included in every report.
- Prevent reversal events from being double-counted or misrepresented; document the simulation's event model.
- For MVP, it is acceptable to report each event's positive source amount and show status/type separately, provided the metric definition explains this convention.

### 10.3 Required Reports

#### Report A — Daily Activity

- Event count by date
- Completed event count by date
- Transaction event value by date and selected currency
- Daily status distribution

#### Report B — Deposits and Withdrawals

- Count and value of deposits
- Count and value of withdrawals
- Date trend
- Clearly documented inclusion/exclusion of statuses

#### Report C — Branch and Channel

- Event counts by branch
- Event value by branch and currency
- Transaction count by channel
- Filters for dates, types, and statuses

#### Report D — Data Quality

- Rejected rows by rule code
- Rejection percentage with a defined denominator
- Warning counts by batch
- Reconciliation failures

#### Report E — Pipeline Operations

- Batch status history
- Batch duration
- Extracted/staged/accepted/rejected/inserted/updated/skipped counts
- Error summaries and latest failed batch

---

## 11. Dashboard Plan

Choose **one** dashboard tool for the MVP: Power BI if it is already available to you, otherwise Metabase is a suitable option. Do not spend time building both until the pipeline is reliable.

### Page 1: Overview

- Completed transaction count
- Completed transaction event value by currency
- Number of processed batches
- Latest pipeline status
- Daily trend line
- Transaction status breakdown

### Page 2: Transaction Analysis

- Deposits versus withdrawals over time
- Breakdown by transaction type
- Branch and channel activity
- Date, status, branch, and currency filters

### Page 3: Pipeline and Data Quality

- Latest batch and overall status
- Row counts by pipeline stage
- Rejection percentage and top validation codes
- Batch duration trend
- Reconciliation status and failure explanation

### Dashboard Acceptance Rules

- Every KPI has a definition in the documentation.
- Filters must not accidentally mix currencies.
- Totals must reconcile with direct SQL queries.
- Charts must distinguish event count from monetary value.
- Missing data should display honestly rather than as a misleading zero.
- A dashboard screenshot may be included in the README, but it must show results generated by the actual project.

---

## 12. SQL Work Items

Create a documented SQL examples file or `sql/analytics/` directory with at least these examples:

1. Daily event count and value
2. Completed events by status and type
3. Deposits versus withdrawals by date
4. Branch-level event count and value
5. Rejected rows by quality rule
6. Duplicate event IDs in staging
7. Rows with missing or unresolved account references
8. Latest ETL batches and durations
9. Window-function example such as daily change in event count using `LAG()`
10. A query-plan demonstration using `EXPLAIN ANALYZE` on a suitable query

For each query, document its question, assumptions, and expected output columns. Use realistic indexes only where the query workload justifies them.

### SQL Quality Requirements

- Use explicit column names rather than `SELECT *` in reporting queries.
- Use clear aliases and consistent formatting.
- Parameterize dynamic query filters in application code.
- Avoid divide-by-zero in percentage calculations.
- Use window functions and CTEs only when they improve readability or solve a real requirement.
- Run and verify each query against generated data before documenting results.

---

## 13. Testing Plan

### 13.1 Unit Tests

Test small functions in isolation:

- Amount parsing and precision
- Timestamp parsing and timezone handling
- Category normalization
- Transaction-type mappings
- Required-field validation
- Duplicate-key detection
- Business-rule validation
- Data-quality reason generation
- Reconciliation calculations
- File fingerprint calculation if used

### 13.2 Integration Tests

Use a dedicated test PostgreSQL database that is never the developer's production or shared database.

Test:

- Database schema initialization
- Staging insertion
- Dimension loading and key resolution
- Fact loading
- Constraints and unique-key behavior
- Rollback when a load fails
- Batch state transitions
- Quality issue insertion
- Idempotent reruns
- Reconciliation outputs

### 13.3 End-to-End Tests

1. Generate a deterministic fixture.
2. Initialize a clean test database.
3. Run the pipeline.
4. Check expected row counts and quality issues.
5. Query the warehouse for expected facts.
6. Re-run the same source.
7. Verify the warehouse fact count is unchanged and the replay is tracked.
8. Execute reporting queries and verify expected results.

### 13.4 Failure-Injection Tests

- Missing input file
- Malformed CSV structure
- Database unavailable before extraction/load
- Database failure during load
- Duplicate source events
- Late-arriving records
- Invalid dimension reference
- Empty file
- Partially valid batch
- Re-run after a failed attempt

### 13.5 Test Data Rules

- Use known expected outputs for all core fixtures.
- Avoid relying on random unseeded data in assertions.
- Keep test fixtures small and readable.
- Clean up test data safely and only within the dedicated test database.
- Never run destructive test cleanup against a production database.

---

## 14. Error Handling, Logging, and Observability

### 14.1 Logging

Logs should contain:

- Timestamp
- Log level
- Batch ID
- Pipeline phase
- Source file or source ID where safe
- Counts and duration
- Error code and a concise message

Do not log passwords, access tokens, database connection strings, or unnecessary personal-like data.

### 14.2 Error Classes

Distinguish among:

- Input/file-contract errors
- Row validation errors
- Transformation errors
- Database constraint errors
- Infrastructure/connection errors
- Unexpected application errors

Each category should have a predictable handling policy and user-readable message.

### 14.3 Recovery Policy

- Do not report success when a transaction failed to commit.
- Roll back warehouse writes that are part of a failed atomic unit.
- Preserve batch metadata and a safe error summary.
- Allow safe reruns after fixing the cause.
- Do not automatically retry non-transient errors without a policy.
- If row-level rejects are expected, continue processing valid rows where the batch policy allows it.

---

## 15. Security and Responsible Data Use

- Use synthetic data exclusively.
- Keep `.env` out of Git and include `.env.example` with placeholders only.
- Use least-privilege database credentials for application access.
- Separate local developer and test database configuration.
- Use parameterized SQL.
- Validate file paths and input formats.
- Avoid exposing raw row payloads in logs or dashboard URLs.
- Do not expose the database directly to the public internet for a portfolio demo.
- If a hosted dashboard/database is used, publish only generated data and rotate any accidentally exposed credential immediately.
- State clearly in the README that BankFlow is an educational prototype and not an official banking or financial system.

---

## 16. Repository Structure

Suggested structure; adapt only when implementation needs justify a change:

```text
BankFlow/
├── README.md
├── plan.md
├── pyproject.toml
├── .env.example
├── .gitignore
├── Dockerfile                    # optional after local MVP
├── docker-compose.yml             # optional after local MVP
├── config/
│   └── settings.yaml
├── data/
│   ├── raw/                       # generated inputs; exclude large outputs from Git
│   └── samples/                   # small synthetic fixtures safe to commit
├── sql/
│   ├── 01_create_schemas.sql
│   ├── 02_staging_tables.sql
│   ├── 03_monitoring_tables.sql
│   ├── 04_dimensions.sql
│   ├── 05_fact_transactions.sql
│   ├── 06_indexes.sql
│   ├── 07_reporting_views.sql
│   └── analytics/
│       ├── daily_activity.sql
│       ├── deposits_withdrawals.sql
│       ├── branch_activity.sql
│       └── data_quality.sql
├── src/
│   └── bankflow/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── db.py
│       ├── generator/
│       ├── extraction/
│       ├── validation/
│       ├── transformation/
│       ├── loading/
│       ├── analytics/
│       ├── monitoring/
│       └── etl.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── end_to_end/
│   └── fixtures/
├── dashboards/
├── docs/
│   ├── architecture.md
│   ├── data_dictionary.md
│   ├── data_quality_rules.md
│   ├── metric_definitions.md
│   └── design_decisions.md
└── .github/
    └── workflows/
        └── ci.yml
```

### Repository Hygiene

- Commit source code, SQL, documentation, and small synthetic fixtures.
- Do not commit local secrets, virtual environments, cache folders, database dumps, or huge generated datasets.
- Include setup commands that work from a clean clone.
- Keep the `main` branch runnable and use feature branches for substantial tasks if working through GitHub.

---

## 17. Four-Week Implementation Roadmap

The schedule assumes roughly 2–3 focused hours per day, with flexibility for coursework. The milestones depend on completion criteria, not simply elapsed time.

### Week 1 — Environment, Data Contract, and Database Foundation

**Objective:** Establish a working database foundation and repeatable synthetic input.

Tasks:

1. Create the GitHub repository and baseline README.
2. Create Python project configuration and a virtual environment.
3. Configure local PostgreSQL and environment variable loading.
4. Create generator functions for customers, accounts, branches, and transactions.
5. Add deterministic generation using a seed.
6. Define source schemas and validation rules.
7. Create staging and monitoring tables.
8. Load a small clean CSV into staging.
9. Add initial database initialization script and smoke test.

Deliverables:

- Repository structure
- `.env.example` and `.gitignore`
- Synthetic clean dataset
- Data contract and initial data dictionary
- Schema initialization scripts
- Successful staging load

**Week 1 exit criteria:** From a clean local environment, generated source data can be loaded into staging and row counts are reported.

### Week 2 — Validation, Transformation, Warehouse Loading

**Objective:** Complete the first end-to-end ETL path.

Tasks:

1. Implement batch registration and state tracking.
2. Implement file-level schema validation.
3. Implement row-level validation and quality issue recording.
4. Implement clean normalization and mapping functions.
5. Create dimension tables and load logic.
6. Create fact table and unique event identity constraint.
7. Implement transaction-safe, idempotent loading.
8. Add reconciliation calculations and run summary.
9. Test valid, rejected, duplicate, and unresolved-reference records.

Deliverables:

- Working CLI or script to process a transaction file
- Validation rule catalogue
- Quality issue/quarantine workflow
- Populated warehouse tables
- Reconciliation output
- Idempotent replay behavior

**Week 2 exit criteria:** A mixed-quality batch is processed deterministically and every source row has a documented outcome under the rules.

### Week 3 — SQL Analytics and Dashboard

**Objective:** Provide useful reports backed by verified queries.

Tasks:

1. Write and verify daily activity SQL.
2. Write and verify deposit/withdrawal summaries.
3. Write branch/channel reporting SQL.
4. Write data-quality and batch-monitoring queries.
5. Create reporting views where useful.
6. Add appropriate indexes based on actual query patterns.
7. Create one dashboard tool's data connection.
8. Build overview, transaction analysis, and data-quality pages.
9. Compare dashboard metrics against direct SQL results.

Deliverables:

- SQL analytics folder
- Reporting views
- Dashboard
- Metric definitions
- Query assumptions and sample screenshots generated by the project

**Week 3 exit criteria:** The dashboard displays correct results, and the key totals can be reproduced with documented SQL.

### Week 4 — Tests, Failure Recovery, Documentation, Demo

**Objective:** Make the project robust and reviewable.

Tasks:

1. Complete unit tests for transformations and validation.
2. Add PostgreSQL integration tests.
3. Add an end-to-end test for initial load and replay.
4. Test failure and recovery paths.
5. Configure GitHub Actions to run lint/type checks if included and tests.
6. Improve error messages, logging, and batch summaries.
7. Finalize architecture and data dictionary documents.
8. Verify clean-clone setup on a fresh environment.
9. Record a short demo or create a reproducible screenshot sequence.
10. Update README with known limitations and measured results only.

Deliverables:

- Passing automated tests
- CI workflow
- Documented setup and troubleshooting
- Architecture and schema documentation
- Reproducible demo
- Final limitations and extension roadmap

**Week 4 exit criteria:** A reviewer can recreate the core project and verify results from documentation without needing undocumented manual steps.

---

## 18. Prioritized Backlog

### P0 — Required for MVP

- [ ] Repository and environment setup
- [ ] Synthetic data generator with deterministic seed
- [ ] Source schemas and documented data contract
- [ ] PostgreSQL staging schema
- [ ] Batch tracking and statuses
- [ ] Row-level validation and issue records
- [ ] Dimension and fact tables
- [ ] ETL orchestration
- [ ] Transaction-safe load
- [ ] Idempotency and replay test
- [ ] Reconciliation output
- [ ] Five core analytical SQL queries
- [ ] Automated tests
- [ ] README with setup instructions

### P1 — Required for Strong Portfolio Presentation

- [ ] Dashboard using one tool
- [ ] CI tests on GitHub Actions
- [ ] SQL indexes with documented rationale
- [ ] Error logging and batch monitoring
- [ ] End-to-end and failure-injection tests
- [ ] Architecture diagram
- [ ] Data dictionary and quality-rule documentation
- [ ] Demo dataset and screenshots
- [ ] Verified performance benchmark on a defined dataset

### P2 — Optional Extensions

- [ ] Docker Compose local setup
- [ ] Incremental processing/watermarks
- [ ] SCD Type 2 dimension
- [ ] Airflow orchestration
- [ ] Oracle/PLSQL extension
- [ ] Additional data-quality framework
- [ ] Query-plan comparison and optimization report

---

## 19. Acceptance Criteria

The MVP is accepted only when the applicable criteria below are verified.

### Functional

- [ ] Synthetic datasets can be generated reproducibly.
- [ ] Source files are checked against documented schemas.
- [ ] Raw records and source metadata are preserved in staging.
- [ ] Invalid rows produce structured issue records.
- [ ] Valid records load into correctly related dimensions and facts.
- [ ] A batch has a traceable status and final count summary.
- [ ] Required analytical SQL queries run successfully.
- [ ] Dashboard output matches direct SQL for selected metrics.

### Correctness and Reliability

- [ ] The chosen event key is documented and enforced by a database constraint.
- [ ] Re-running an already processed input does not create duplicate facts.
- [ ] A failing load does not leave a logically partial warehouse update.
- [ ] Source-to-target outcomes reconcile under documented rules.
- [ ] Invalid records are not silently discarded.
- [ ] Currency aggregation and transaction status semantics are clearly defined.
- [ ] Late-arriving events follow a documented policy, even if advanced incremental handling is deferred.

### Quality and Delivery

- [ ] Unit tests cover core validation/transformation logic.
- [ ] Integration tests use a separate test database.
- [ ] End-to-end test covers load, query, and replay.
- [ ] CI runs tests automatically.
- [ ] A clean clone can be configured by following the README.
- [ ] No secrets or non-synthetic financial/customer records are committed.
- [ ] Documentation states known limitations and does not claim unmeasured results.

### Performance Targets (Planning Targets, Not Claims)

- [ ] Process a 10,000-row synthetic development dataset on the developer's machine.
- [ ] Record elapsed time, accepted/rejected counts, and environment details.
- [ ] If optimizing, compare against a reproducible baseline and explain the change.

Performance targets should be refined after the basic implementation is measured. Do not treat a machine-specific runtime as a universal performance promise.

---

## 20. Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Scope grows too quickly | MVP remains unfinished | Complete all P0 items before extensions |
| Monetary calculations use floating point | Inaccurate totals | Use decimal parsing and PostgreSQL `NUMERIC` |
| Duplicate detection is only in Python | Concurrent/repeated loads can duplicate facts | Enforce database uniqueness and test replay |
| Invalid rows disappear during parsing | Reconciliation becomes impossible | Preserve staging values and record rejects explicitly |
| Dashboard definitions differ from SQL | Misleading metrics | Document metrics and reconcile dashboard outputs to SQL |
| Ambiguous currency aggregation | Incorrect totals | Filter/group by currency or implement an explicit conversion model |
| Transaction status semantics are unclear | Double-counted or misleading reports | Define event and status semantics before writing reports |
| Tests touch the wrong database | Data loss or pollution | Separate test database and validate test configuration |
| Secrets are committed | Credential exposure | `.gitignore`, placeholders, repository checks, rotate exposed credentials |
| External service becomes unavailable | Demo fails | Keep the core pipeline local and avoid unnecessary external dependencies |
| Project contains fabricated performance claims | Interview credibility loss | Benchmark actual code and retain reproducible test/benchmark instructions |

---

## 21. Documentation Deliverables

### README.md

Include:

1. Project purpose and educational disclaimer
2. Feature overview
3. Architecture diagram
4. Technology stack
5. Prerequisites
6. Environment configuration
7. Database initialization
8. Data generation instructions
9. ETL run instructions
10. How to inspect rejected rows and batch outcomes
11. Sample SQL analytics
12. Dashboard setup and screenshots
13. Testing commands
14. Reproducible benchmark method and actual results once measured
15. Known limitations and next steps

### `docs/architecture.md`

Explain component responsibilities, layer boundaries, data flow, batch lifecycle, transaction boundaries, and failure recovery.

### `docs/data_dictionary.md`

Document table and column definitions, types, nullable status, key constraints, source-to-target mapping, and business meaning.

### `docs/data_quality_rules.md`

List rule codes, severity, exact condition, response, and a sample failing row.

### `docs/metric_definitions.md`

Define every dashboard metric and how statuses, transaction types, currencies, reversals, and dates are treated.

### `docs/design_decisions.md`

Record key decisions and alternatives considered, including:

- Why PostgreSQL and Python were selected
- Why the project begins with batch ETL
- Why raw staging is retained
- How idempotency is enforced
- How the event identity is chosen
- How rejected rows are represented
- Why dashboard metrics are computed from reporting SQL
- Which extensions were intentionally deferred

---

## 22. Interview Preparation

Be prepared to explain the design, trade-offs, and failure behavior in your own words.

1. What is ETL, and why does BankFlow need each stage?
2. What is the difference between staging, operational tables, and a data warehouse?
3. Why is a star schema suitable for analytical reporting?
4. What is the grain of the fact table?
5. What is a surrogate key and why use one in a dimension?
6. How do primary keys, foreign keys, and unique constraints protect correctness?
7. What is idempotency and how does the implementation guarantee it?
8. What happens if the database fails halfway through a load?
9. How do you distinguish a rejected row from a failed batch?
10. How does source-to-target reconciliation work?
11. Why use a decimal/numeric type for amounts?
12. How are reversals and failed transactions represented?
13. Why should event values in different currencies not be added without conversion rules?
14. What index did you add, why, and how did you verify its benefit?
15. How does an inner join differ from a left join in quality checks?
16. How can `ROW_NUMBER()` help detect duplicates?
17. What is the difference between a fact table and a dimension table?
18. What is a late-arriving event and how should it be handled?
19. How do unit, integration, and end-to-end tests differ?
20. What would change when moving from a local prototype to a production data platform?

Do not memorize answers without understanding the actual code. The project is most useful when each answer can be connected to a specific implementation or test.

---

## 23. Resume Usage Policy

Use a resume entry only after the corresponding feature exists and has been verified. Possible wording after implementation:

**BankFlow — Banking Transaction ETL & Analytics Warehouse**  
*Python, SQL, PostgreSQL, Pandas, pytest, GitHub Actions, Power BI/Metabase*

- Designed a dimensional PostgreSQL warehouse with transaction facts and customer, account, branch, and date dimensions for analytical reporting.
- Developed a Python ETL pipeline to ingest, validate, transform, and load synthetic banking transactions with rejected-record tracking and batch reconciliation.
- Implemented SQL reports for transaction trends, branch activity, and data-quality monitoring, with dashboard metrics verified against direct queries.
- Added automated tests and CI checks for validation rules, loading correctness, and repeatable batch execution.

Remove technologies or bullets that have not been implemented. Add numerical performance claims only after you have collected repeatable measurements and can explain the benchmark methodology.

---

## 24. Definition of Done

BankFlow is complete for the first portfolio release when:

- The repository can be built from a fresh clone using documented commands.
- The synthetic dataset is reproducible and contains both clean and known-bad scenarios.
- The pipeline completes a batch with structured status and counts.
- Raw staging is preserved and rejects are inspectable.
- Dimension/fact relationships and constraints are enforced by PostgreSQL.
- Replaying a batch does not duplicate facts.
- Transaction boundaries, failure handling, and reconciliation behavior are demonstrated by tests.
- Core SQL queries produce verified outputs.
- Dashboard figures match their SQL definitions.
- Unit, integration, and end-to-end tests pass in the intended environment.
- CI executes the relevant checks.
- README and supporting documentation describe actual behavior, limitations, and reproducible results.
- No secrets or real customer/banking data are committed.

**Recommended implementation order:** schema and sample data → staging → validation → warehouse load → idempotency → reconciliation → SQL reports → dashboard → tests/CI hardening → documentation and demo. This order prioritizes correctness before presentation.
