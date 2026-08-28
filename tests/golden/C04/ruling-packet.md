# Domain ruling required — C04 / AQ-001

**Were all payments recorded before the currency field existed denominated in USD, or must their currency be sourced per organisation?**

Requires: Finance operations owner with authority over historical payment records

## Why this cannot be settled from the data

The value was never recorded. No table, constraint, or audit event distinguishes a payment that was USD from one whose currency was simply not captured. Any answer the system produced would be a guess wearing the costume of a migration.

## Affected rows

`payments` where `currency_code IS NULL` — 2 row(s)

- organisation `11111111-1111-4111-8111-111111111111`: 1 row(s)
- organisation `22222222-2222-4222-8222-222222222222`: 1 row(s)

## Interpretations

### All historical payments were denominated in USD

Every payment recorded before the currency field existed was in US dollars, so backfilling USD restores information that was always true but never stored.

If this is wrong: Payments made in another currency are relabelled as USD. Amounts are unchanged, so nothing fails a constraint, and every later reconciliation, report, and audit silently uses the wrong currency for those rows.

### Currency varied by organisation and cannot be assumed

Organisations operating in different regions recorded payments in local currency. The absent field means unknown, not USD, and the correct value must come from an external record.

If this is wrong: The migration is blocked and the field stays nullable for longer than necessary. Reporting remains incomplete until the true currency is sourced, but nothing is misstated.

## Evidence already checked

- payments.currency_code has no default and no check constraint
- no audit_events row records a currency for the affected payments
- the currencies table lists USD, KES and JPY, so more than one was in use
- at least one affected organisation has other payments denominated in KES

## Affected invariants

INV-MONEY-002

## To rule

Record a scoped ruling with a determination and a justification. A
free-form approval is not a ruling and will be rejected: the answer has
to compile into a check. A ruling cannot override a failure the
database already demonstrated.
