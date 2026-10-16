# BankFlow — Data Quality Rules

> Status: proposed rule catalogue. Update rule behavior, severity, and tests to match the actual validator. Data-quality behavior is a public contract and must not be changed silently.

## 1. Severity Levels

- **ERROR** — the row or file cannot be treated as valid under the current contract.
- **WARNING** — data may be accepted, but a potential issue should be made visible.
- **INFO** — an expected operational disposition, such as a safely skipped replay.

File-level errors and row-level errors must be distinguishable. A file with missing required headers generally fails before row-level processing. A malformed row should be preserved and recorded whenever parsing makes that possible.

## 2. Proposed Rule Catalogue

| Rule code | Scope | Condition | Proposed severity | Expected disposition |
|---|---|---|---|---|
| `FILE_REQUIRED_COLUMN_MISSING` | File | Required source header is absent | ERROR | Fail the file/batch with a useful message |
| `FILE_UNREADABLE` | File | Encoding or CSV parse prevents safe reading | ERROR | Fail batch; preserve batch failure metadata |
| `FILE_EMPTY` | File | File contains headers but no rows | Policy-defined | Record a clear empty-input result; do not fake success with invented rows |
| `TXN_ID_MISSING` | Row | Required transaction ID is empty | ERROR | Quarantine/reject |
| `TXN_ID_DUPLICATE` | Row/event | Duplicate ID inside a source file with ambiguous event identity | Policy-defined | Apply explicit duplicate policy and record disposition |
| `SOURCE_REPLAY_SKIPPED` | Event | An immutable event is already present in warehouse | INFO | Safely skip and count it |
| `ACCOUNT_ID_MISSING` | Row | Required account ID is empty | ERROR | Reject/quarantine |
| `ACCOUNT_NOT_FOUND` | Row | Account reference cannot be resolved | ERROR | Reject/quarantine unless a documented late-arrival path applies |
| `AMOUNT_MISSING` | Row | Required amount is absent | ERROR | Preserve source value; reject |
| `AMOUNT_PARSE_ERROR` | Row | Amount cannot be parsed as a decimal | ERROR | Preserve raw value; reject |
| `AMOUNT_RULE_VIOLATION` | Row | Amount violates an explicitly defined transaction-type rule | ERROR or WARNING | Follow the specified type-specific contract |
| `TIMESTAMP_PARSE_ERROR` | Row | Timestamp cannot be parsed with supported formats | ERROR | Reject; do not substitute current time |
| `TYPE_UNSUPPORTED` | Row | Transaction type has no mapping | ERROR | Reject until mapping is intentionally added |
| `STATUS_UNSUPPORTED` | Row | Status is outside the configured allowed set | ERROR | Reject |
| `CHANNEL_UNSUPPORTED` | Row | Channel is outside the configured allowed set | ERROR | Reject or flag per contract |
| `CURRENCY_MISSING` | Row | Currency is required but absent | ERROR | Reject |
| `CURRENCY_UNSUPPORTED` | Row | Currency is not supported in this dataset/configuration | ERROR | Reject or quarantine |
| `SOURCE_REFERENCE_MISSING` | Row | Required customer/branch/account reference is unresolved | ERROR | Reject or apply documented unknown-member policy |
| `LOW_DAILY_VOLUME` | Aggregate | Volume falls below a configurable threshold | WARNING | Report; do not automatically alter underlying data |
| `CONFLICTING_REPLAY_PAYLOAD` | Event | Existing source ID has a different payload under immutable-event assumption | ERROR | Flag conflict; do not silently overwrite |

These rule codes are proposals based on `plan.md`. During implementation, avoid duplicate codes with overlapping meaning; choose a stable catalogue and test it.

## 3. Quality Issue Record

Each issue should record as applicable:

- unique issue ID
- batch ID
- source row ID or row number
- source filename/source identifier
- stable rule code
- severity
- plain-language explanation
- detection timestamp
- disposition (`REJECTED`, `WARNED`, `SKIPPED`, or another documented enum)

Avoid logging secrets or unnecessary source payloads. Link back to staged source data rather than copying large/full rows into error logs by default.

## 4. Rules for Rule Implementation

1. Rule codes must be stable and machine-readable.
2. Human-readable reason text should be clear but need not be used as a programmatic key.
3. The same input should produce the same validation outcome under the same configuration.
4. State whether all detectable issues are recorded for a row or validation stops after the first fatal issue.
5. Tests should assert codes and dispositions, not just that an exception was raised.
6. Quality issues must feed reconciliation counts.
7. Rejected records must not silently enter valid warehouse facts.
8. Duplicate events, reversals, and transaction corrections must be distinguished by documented semantics.

## 5. Phase Gate

The validation phase is not complete until every defect fixture has an expected result, the validator produces that result, and row/batch reconciliation accounts for all records under the documented policy.
