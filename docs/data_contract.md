# BankFlow — Source Data Contract

> This is the planned contract for synthetic CSV inputs. During Phase 1, align the actual schemas and parser behavior with this file. Any deviation must be documented and tested.

## 1. General Conventions

- All records are generated synthetic data. Do not use real bank/customer data.
- CSV files should have UTF-8 encoding and a single header row.
- Header names are exact and documented. Missing required headers are file-level errors.
- Empty strings and whitespace-only strings should be treated as missing for required text fields.
- Source IDs are business identifiers; warehouse surrogate keys are separate.
- Source timestamp format(s) must be documented and parsed explicitly. Do not guess ambiguous dates silently.
- Monetary amounts must be parsed as decimal values and stored as PostgreSQL `NUMERIC` with defined precision/scale.
- Currency must be represented explicitly. Do not aggregate amounts across currencies unless grouped by currency or converted using a documented FX model.
- All source files and records should be associated with a source system/name and ingestion batch.

## 2. Planned Source Files

The generator may emit separate CSVs for each entity. Exact filenames are finalized during implementation; recommended filenames are `customers.csv`, `accounts.csv`, `branches.csv`, and `transactions.csv`.

### 2.1 `branches.csv`

| Field | Required | Contract / notes |
|---|---:|---|
| `branch_id` | Yes | Stable synthetic source ID; unique within the source set. |
| `branch_name` | Yes | Synthetic display name. Avoid real branch claims. |
| `region` | Yes | Synthetic region/category code. |

### 2.2 `customers.csv`

| Field | Required | Contract / notes |
|---|---:|---|
| `customer_id` | Yes | Stable synthetic ID, unique within source set. |
| `customer_segment` | Yes | Must belong to the configured set of customer segments. |
| `created_date` | Yes | Explicit date format, preferably ISO `YYYY-MM-DD`. |
| `customer_status` | Yes | A documented supported status. |

Avoid generating customer names, phone numbers, email addresses, postal addresses, identity numbers, or other unnecessary personal fields. Opaque IDs are sufficient for the MVP.

### 2.3 `accounts.csv`

| Field | Required | Contract / notes |
|---|---:|---|
| `account_id` | Yes | Stable synthetic ID, unique within source set. |
| `customer_id` | Yes | Must resolve to a generated customer unless intentionally injected as a defect. |
| `branch_id` | Yes | Must resolve to a generated branch unless intentionally injected as a defect. |
| `account_type` | Yes | One of the documented supported account types. |
| `account_status` | Yes | One of the documented supported statuses. |
| `opened_date` | Yes | Explicit date format, preferably ISO. |
| `currency` | Yes | Supported currency code from configuration. |

### 2.4 `transactions.csv`

| Field | Required | Contract / notes |
|---|---:|---|
| `transaction_id` | Yes | Stable source event ID under the MVP immutable-event assumption. |
| `account_id` | Yes | Must resolve to a known account unless the row is a deliberate reference defect. |
| `transaction_type` | Yes | Explicitly enumerated event type. |
| `amount` | Yes | Decimal-formatted value, no locale-dependent separators. Amount rules are type-specific. |
| `currency` | Yes | Supported currency code; source-to-account currency consistency must be defined. |
| `transaction_timestamp` | Yes | ISO 8601 timestamp with timezone offset preferred. |
| `status` | Yes | Documented event-processing status. |
| `channel` | Yes | Documented channel category. |
| `counterparty_account_id` | No | Optional; required only for defined transfer event types if included in the MVP rules. |
| `source_system` | Yes | Synthetic identifier for the event-producing source. |

The transaction row represents an event, not a balance snapshot. A transfer may require linked debit/credit events, but that behavior should only be implemented if the generator and model explicitly define it. Reversals are separate documented events where appropriate and must not be mistaken for accidental duplicates.

## 3. Supported Values

Create a single configuration/constant source for allowed values. Do not copy independent lists across generator, validation code, and tests.

- Transaction types: start with `DEPOSIT`, `WITHDRAWAL`, `TRANSFER`, `PAYMENT`, `FEE`, `REVERSAL` if their semantics are implemented. Remove any unsupported type until its behavior is defined.
- Statuses: use an explicit set such as `PENDING`, `COMPLETED`, `FAILED`, `REVERSED`, and define how each status affects metrics.
- Channels: use a documented set such as `BRANCH`, `ATM`, `ONLINE`, `MOBILE`.
- Currencies: configure a small set for tests. The simplest MVP can use one currency to avoid cross-currency totals; if multiple currencies are enabled, all relevant reports must group by currency.
- Account/customer statuses and types: list the exact allowed values in configuration and documentation.

These examples are proposed values, not a claim that the final implementation already accepts them.

## 4. Missing, Malformed, and Invalid Values

- Missing required transaction ID: reject/quarantine with stable code `TXN_ID_MISSING`.
- Duplicate transaction event identity: apply documented source identity/replay policy; do not blindly drop the first or later row.
- Missing/unparseable amount: preserve the raw representation and report `AMOUNT_PARSE_ERROR` or another precise code.
- Amount outside a type-specific allowed range: use `AMOUNT_RULE_VIOLATION` only if the relevant transaction type contract defines the rule.
- Malformed timestamp: reject with `TIMESTAMP_PARSE_ERROR`; do not substitute the current time.
- Unknown account reference: reject/quarantine as `ACCOUNT_NOT_FOUND` unless a documented late-arriving-reference policy applies.
- Unsupported type/status/channel/currency: reject or flag according to a documented deterministic rule.
- Missing required file header: file-level failure, for example `FILE_REQUIRED_COLUMN_MISSING`.
- Duplicate replay of already-loaded source event: safely skip/update/flag according to event-identity policy and record the disposition.

A row can have multiple validation issues. The implementation must decide whether to record all detectable issues or stop at a fatal rule, and tests must reflect that choice.

## 5. Defect Injection Contract

The generator should support clean mode and configurable defect injection. Each defect scenario needs an expected result in a test fixture.

Required scenarios from the master plan:

1. Missing transaction ID.
2. Duplicate event ID.
3. Missing account ID.
4. Unknown account reference.
5. Unsupported transaction type.
6. Missing currency.
7. Invalid timestamp text.
8. Missing amount.
9. Non-numeric amount.
10. Type-specific amount rule violation.
11. Unsupported status.
12. Replay of previously loaded input.
13. Required header missing/mismatched.
14. Empty file.
15. Late-arriving event with an earlier event timestamp.

Do not assume every defect belongs in the same generated file. Independent fixtures can make validation outcomes easier to assert.

## 6. Staging Preservation and Lineage

For every ingested row, preserve where possible:

- source filename or source URI/path as a relative/non-sensitive label
- 1-based source row number
- batch ID
- ingestion timestamp
- original source values or raw row representation
- parse/validation disposition

Malformed row-level data must not disappear simply because casting failed. File-level failures should be represented as a failed batch with a reason, rather than fabricated as a successful empty batch.

### Raw Staging Preservation and Surplus Fields Policy

1. **Exact Raw Value Preservation:** All source field values must be stored in staging columns and `raw_payload` (JSONB) exactly as read from the CSV file. Ingestion methods must never trim leading/trailing whitespace, normalize empty values, or alter case.
2. **Surplus Fields Representation:** If a CSV data row contains more fields than the declared header schema, the extra fields must not be discarded. They are preserved in `raw_payload` under the reserved key `_surplus` as an array of strings (e.g., `{"_surplus": ["extra_field_1", "extra_field_2"]}`).
3. **Layer Separation:** Field-level whitespace trimming, canonicalization, type casting, and defect classification belong strictly to the validation and transformation layer (Phase 2 onwards); they must never be mixed into raw staging ingestion.

## 7. Warehouse Identity Rules

- Define transaction event identity before implementation; default assumption is an immutable event ID unique within `source_system`.
- Enforce the chosen identity with a database unique constraint.
- Preserve the source business ID for traceability.
- Decide how source corrections would work; for the MVP, immutable events may be accepted and conflicting content for an already-loaded ID may be flagged instead of silently overwriting it.
- Use surrogate keys for warehouse dimensions.
- Define a strategy for unknown dimension keys; do not invent attributes.

## 8. Metric Semantics

- A transaction count is a count of events satisfying the stated status/type filter, not a count of distinct accounts or a balance.
- Transaction value should say which statuses and types are included.
- Deposits and withdrawals should be separately identified using type mappings.
- Reversal handling must be defined; do not assume a reversal is automatically the same as an original transaction.
- Currency must remain in the grouping key unless a valid conversion mechanism is implemented.
- Rejected staging rows should not appear as accepted warehouse facts.

## 9. Changes to This Contract

Any contract change must update the generator, validators, warehouse mapping, fixtures, and tests together. Record why the change is needed in `docs/design_decisions.md` or the phase log. Never change expected outputs merely to make a failing test pass without checking the underlying semantics.
