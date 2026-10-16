# BankFlow — Metric Definitions

> Status: planned metric contract. SQL views and dashboard labels must match these definitions exactly. Final filters and formulas should be updated after event/status semantics are implemented and tested.

## 1. General Rules

- Every metric definition must specify grain, inclusions/exclusions, grouping dimensions, time semantics, currency semantics, and source/reporting layer.
- Transaction events and account balances are different concepts. Do not present sums of event values as balances.
- Do not aggregate monetary values across currencies without grouping by currency or applying a documented conversion model.
- Dashboard metrics should be calculated by the reporting SQL/views where practical, not by duplicated, inconsistent logic in multiple layers.
- Every metric needs at least one known-answer fixture or reconciliation check.

## 2. Core Metrics

### 2.1 Event Count

**Definition:** Count of fact rows satisfying the selected filters. State whether the metric includes all statuses or only selected statuses. This is an event count, not a count of distinct accounts or customers.

**Required dimensions:** event/reporting date; optionally branch, channel, transaction type, currency, status.

### 2.2 Transaction Event Value

**Definition:** Sum of `amount` for fact rows satisfying explicitly named filters. The dashboard label must state whether this includes completed, pending, failed, reversed, fee, or reversal events.

**Currency rule:** group by currency or keep the MVP to one configured currency. Do not imply converted value unless a conversion model exists.

### 2.3 Daily Activity

**Definition:** event count and event value grouped by the documented reporting date. The reporting date must follow one timezone rule, consistently applied in ETL and SQL.

### 2.4 Deposits and Withdrawals

**Definition:** separately aggregate transaction events mapped to the documented `DEPOSIT` and `WITHDRAWAL` categories, applying the same explicitly selected status filter. Document treatment of corrections/reversals; do not simply subtract all withdrawals and call the result profit or balance.

### 2.5 Branch Activity

**Definition:** event count and event value grouped by the synthetic branch dimension, using the same date/status/currency filters as the overall activity metrics.

### 2.6 Channel Activity

**Definition:** event count and event value grouped by the documented source channel. Unknown channels should be reported/handled by the data contract rather than silently remapped.

### 2.7 Rejection Count

**Definition:** count of rejected source rows under the chosen row disposition semantics. Decide whether the chart counts rejected rows or individual issue records; these are not the same when one row can violate multiple rules.

### 2.8 Rejection Rate

**Proposed formula:** `rejected_rows / evaluated_rows * 100` where `evaluated_rows` is defined consistently as staged rows with a completed validation disposition. Avoid dividing by zero; show no value or `N/A` when no rows were evaluated.

### 2.9 Batch Reconciliation Status

**Definition:** result of comparing all required source/staging/validation/loading counts and any comparable value totals under the documented contract. A reconciliation status must not be marked `PASS` if relevant rows lack a disposition.

### 2.10 Pipeline Duration

**Definition:** batch completion timestamp minus start timestamp for runs with both timestamps. State whether this includes file discovery, extraction, validation, loading, and reconciliation. Failed/incomplete runs should be represented separately.

## 3. Count Reconciliation

The implementation should define count identities based on its actual disposition states. A generic pattern is:

`staged_rows = accepted_rows + rejected_rows + intentionally_skipped_rows`

This identity is only valid if those dispositions are mutually exclusive and cover all staged rows. If the design has file-level unprocessed input or multiple passes, represent those explicitly rather than forcing an incorrect equation.

For accepted records, define whether the outcome count is `inserted + updated + already_present_skipped` and ensure those buckets are mutually exclusive per run.

## 4. Dashboard Pages

### Overview

- Completed transaction/event count under a named status filter.
- Transaction event value, grouped by currency.
- Daily trend.
- Clearly labelled rejected/reversed/failed indicators where implemented.

### Transaction Analysis

- Deposit and withdrawal activity by date.
- Event count/value by branch and channel.
- Transaction type distribution.

### Pipeline and Data Quality

- Batch status and duration.
- Source/staged/accepted/rejected/inserted/updated/skipped counts.
- Top issue codes.
- Reconciliation outcome.

## 5. Metric Verification

For every displayed metric:

1. Write a SQL query/view with a documented definition.
2. Create a synthetic fixture with a small known dataset.
3. Assert the SQL result in a test or reproducible verification query.
4. Compare dashboard output to the authoritative SQL result.
5. Save the applied filters and relevant currency/time semantics with demo evidence.

Do not use ambiguous labels such as `Revenue`, `Net Profit`, or `Account Balance` unless the model genuinely defines and verifies those measures.
