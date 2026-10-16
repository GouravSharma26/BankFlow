# BankFlow — Data Quality Rules

> Status: Authoritative rule catalogue implemented and verified in Phase 2. Data-quality behavior is a public contract.

## 1. Severity Levels

- **ERROR** — the row or file cannot be treated as valid under the current contract. Produces `REJECTED` disposition and sends row to quarantine.
- **WARNING** — data may be accepted, but a potential issue is tracked and reported. Produces `WARNED` disposition.
- **INFO** — an expected operational disposition, such as a safely skipped replay in warehouse ingestion (Phase 3).

File-level errors and row-level errors are strictly distinguished. A file with missing required headers or empty contents fails during staging ingestion prior to row-level validation. A malformed row is preserved in staging exactly as ingested and tracked in quarantine and monitoring tables.

## 2. Authoritative Rule Catalogue

| Rule code | Scope | Condition | Severity | Disposition |
|---|---|---|---|---|
| `FILE_REQUIRED_COLUMN_MISSING` | File | Required source header column is absent | ERROR | Fails batch with clear diagnostic message |
| `FILE_HEADER_MISMATCH` | File | Unexpected extra or duplicate columns present | ERROR | Fails batch |
| `FILE_UNREADABLE` | File | Encoding or CSV parse prevents safe reading | ERROR | Fails batch; preserves error summary |
| `FILE_EMPTY` | File | File contains 0 bytes or header only without data rows | ERROR | Fails batch; prevents phantom batches |
| `BATCH_ALREADY_EXISTS` | Batch | Attempt to ingest with a pre-existing batch_id | ERROR | Fails ingestion; preserves existing batch state |
| `TXN_ID_MISSING` | Row | Required transaction ID is empty or whitespace | ERROR | REJECTED / Quarantined |
| `TXN_ID_DUPLICATE` | Row | Ambiguous duplicate transaction ID within a batch | ERROR | REJECTED / Quarantined (all occurrences) |
| `ACCOUNT_ID_MISSING` | Row | Required account ID is empty or whitespace | ERROR | REJECTED / Quarantined |
| `ACCOUNT_NOT_FOUND` | Row | Account reference cannot be resolved in staging or prior valid accounts | ERROR | REJECTED / Quarantined |
| `CUSTOMER_ID_MISSING` | Row | Required customer ID is empty or whitespace | ERROR | REJECTED / Quarantined |
| `CUSTOMER_NOT_FOUND` | Row | Customer reference cannot be resolved in staging or prior valid customers | ERROR | REJECTED / Quarantined |
| `BRANCH_ID_MISSING` | Row | Required branch ID is empty or whitespace | ERROR | REJECTED / Quarantined |
| `BRANCH_NOT_FOUND` | Row | Branch reference cannot be resolved in staging or prior valid branches | ERROR | REJECTED / Quarantined |
| `AMOUNT_MISSING` | Row | Required amount field is empty or whitespace | ERROR | REJECTED / Quarantined |
| `AMOUNT_PARSE_ERROR` | Row | Amount cannot be parsed as a finite numeric decimal | ERROR | REJECTED / Quarantined |
| `AMOUNT_RULE_VIOLATION` | Row | Amount violates domain constraint (must be strictly > 0.00) | ERROR | REJECTED / Quarantined |
| `TIMESTAMP_PARSE_ERROR` | Row | Timestamp cannot be parsed as ISO 8601 or lacks explicit timezone offset | ERROR | REJECTED / Quarantined |
| `TYPE_UNSUPPORTED` | Row | Transaction type is not in `SUPPORTED_TRANSACTION_TYPES` | ERROR | REJECTED / Quarantined |
| `STATUS_UNSUPPORTED` | Row | Status is not in `SUPPORTED_TRANSACTION_STATUSES` | ERROR | REJECTED / Quarantined |
| `CHANNEL_UNSUPPORTED` | Row | Channel is not in `SUPPORTED_CHANNELS` | ERROR | REJECTED / Quarantined |
| `CURRENCY_MISSING` | Row | Currency is required but empty or whitespace | ERROR | REJECTED / Quarantined |
| `CURRENCY_UNSUPPORTED` | Row | Currency is not in `SUPPORTED_CURRENCIES` (USD, EUR, GBP) | ERROR | REJECTED / Quarantined |
| `CUSTOMER_SEGMENT_UNSUPPORTED` | Row | Customer segment is not in `SUPPORTED_CUSTOMER_SEGMENTS` | ERROR | REJECTED / Quarantined |
| `CUSTOMER_STATUS_UNSUPPORTED` | Row | Customer status is not in `SUPPORTED_CUSTOMER_STATUSES` | ERROR | REJECTED / Quarantined |
| `ACCOUNT_TYPE_UNSUPPORTED` | Row | Account type is not in `SUPPORTED_ACCOUNT_TYPES` | ERROR | REJECTED / Quarantined |
| `ACCOUNT_STATUS_UNSUPPORTED` | Row | Account status is not in `SUPPORTED_ACCOUNT_STATUSES` | ERROR | REJECTED / Quarantined |
| `SOURCE_REPLAY_SKIPPED` | Event | Immutable event already present in warehouse (Phase 3 dependency) | INFO | SKIPPED |

## 3. Policy Decisions

1. **Multi-Issue Recording Policy:** Validation records **all detectable issues** for a row rather than halting on the first failure. This provides complete diagnostic visibility for upstream data providers.
2. **Batch Accounting Invariant:** A row with multiple issues is counted as **exactly one rejected row** in `records_rejected`. The invariant `records_evaluated = records_valid + records_rejected` is strictly enforced.
3. **Traceability Without Duplication:** Quarantined rows do not duplicate the raw payload or staging columns. The `quarantine.quarantined_records` table holds metadata and references `source_row_id` in staging. A relational view `quarantine.vw_quarantined_transactions` joins them on demand.
4. **Duplicate Transaction Policy:** In a batch, if an ID occurs more than once, it cannot be safely or deterministically loaded into the warehouse. Both/all occurrences of the ambiguous ID are flagged with `TXN_ID_DUPLICATE` and quarantined so neither overwrites the other.
5. **Late-Arriving Events Policy:** Late-arriving events with valid ISO 8601 timestamps with timezone offsets from past dates are **valid events** under our event-driven model and are NOT rejected simply because their timestamp is old.
6. **Reversals Policy:** Reversals are legitimate events (`TYPE_REVERSAL`) with their own immutable event IDs, not duplicates of previous transactions.
7. **Validation Idempotency:** Executing `validate_batch(batch_id)` repeatedly on the same batch clears previous issues and quarantine entries for that batch within a database transaction before re-evaluating, guaranteeing repeatable outcomes without double-counting.
