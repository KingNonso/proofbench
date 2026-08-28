# AidLedger case map

Frozen before any case SQL is written. This is the design check that stops the benchmark
schema from being re-cut at case seven. Every case in PRD §8.2 must have a home in **one**
shared schema.

Required by the Phase 0 exit gate. Changing a row here after cases are built invalidates the
affected golden bundles and must be recorded in `CHANGELOG.md`.

## 1. Shared schema

Six tables. All amounts are integer minor units; no floating point anywhere in the money path.

| Table | Purpose | Tenant key | Notes |
| --- | --- | --- | --- |
| `organizations` | Tenant root | `org_id` (self) | One row per humanitarian organisation |
| `beneficiaries` | People receiving assistance | `org_id` | Synthetic names only |
| `payments` | Payment instructions | `org_id` | The table C01 recreates |
| `disbursements` | Settled money movements | `org_id` | `idempotency_key` unique per org |
| `currencies` | Currency reference | none (global) | `minor_unit_scale` drives all conversion |
| `audit_events` | Immutable history | `org_id` | Append-only, no UPDATE or DELETE grant |

Row-level security is enabled on all five tenant-scoped tables. The tenant is carried in
`current_setting('aidledger.org_id')`, set per session by the connecting application.

## 2. Roles

Cluster-wide objects. Created once at container bootstrap by the container administrator and
**immutable for the life of the container** — this is what makes database-per-world safe.

| Role | Purpose | Key attributes |
| --- | --- | --- |
| `aidledger_admin` | Bootstrap and fixture load | Owns base objects; not used by candidates |
| `aidledger_migration` | Applies the candidate migration | **Restricted:** no `SUPERUSER`, `CREATEROLE`, `CREATEDB`, `REPLICATION`, `BYPASSRLS`, no server-file roles |
| `aidledger_app` | Tenant worker, the running application | Read and write within its own org only |
| `aidledger_org_admin` | Organisation administrator | Wider read within its own org |
| `aidledger_auditor` | Auditor | Read-only, `audit_events` within its own org |
| `aidledger_service` | Background settlement and backfill process | Write to `disbursements`, append to `audit_events` |

The candidate migration runs as `aidledger_migration`, never as superuser. Any candidate that
attempts to acquire a cluster capability is a containment failure, not a passing migration.

## 3. Case map

| ID | Table and column | Role exercised | Required world | Visible test | Evaluator oracle | Expected state | Confirmed blast-radius evidence | State tier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C01 | `payments` recreated, RLS not restored | `aidledger_app` | `rls` | Final columns and a single-tenant read both pass | `expected_blocking_invariant_ids: [INV-RLS-001]` | `BLOCKED` | Rows of org B visible to an org A session; count and sample row ids | DB-local |
| C02 | `payments` policies partially restored | `aidledger_auditor`, `aidledger_org_admin` | `rls` (full role matrix) | App-role read passes | `[INV-RLS-002, INV-RLS-003]` | `BLOCKED` | Auditor denied required rows; org-admin granted rows outside its org | DB-local |
| C03 | `payments.amount_minor` converted via `float8` | `aidledger_service` | `money` | Row count and non-null check pass | `[INV-MONEY-001]` | `BLOCKED` | Exact minor-unit drift per affected row, summed | DB-local |
| C04 | `payments.currency_code` backfilled to `USD` where null | `aidledger_service` | `money` (after ruling) | Not-null constraint check passes | `case_class: authority_required` | `DOMAIN_RULING_REQUIRED` | Count of historical rows with no currency evidence, by org and date range | DB-local |
| C05 | `payments.amount` dropped while v1 still writes it | `aidledger_app` | `rolling` | New-schema test passes | `[INV-COMPAT-001]` | `BLOCKED` | v1 insert fails with SQLSTATE; affected app version and statement | DB-local |
| C06 | `disbursements` backfill without checkpoint or `ON CONFLICT` | `aidledger_service` | `interruption` | Post-backfill row count passes on an uninterrupted run | `[INV-IDEM-001]` | `BLOCKED` | Duplicate disbursement ids and duplicated minor-unit total after resume | DB-local |
| C07 | `payments` index or rewrite holding `ACCESS EXCLUSIVE` beyond budget | `aidledger_migration` | `locks` | Final index exists | `[INV-LOCK-001]` | `BLOCKED` | SQLSTATE `55P03` under the declared budget; lock mode and blocked statement | DB-local, two sessions |
| C08 | `payments` rollback path drops post-start writes | `aidledger_app` | `rollback` | Forward migration test passes | `[INV-ROLLBACK-001]` | `BLOCKED` | Row ids written after migration start and absent after rollback | DB-local |
| C09 | `disbursements.idempotency_key` uniqueness not enforced on retry | `aidledger_service` | `money`, `rolling` | Single-write path passes | `[INV-IDEM-002]` | `BLOCKED` | Two disbursements sharing an idempotency key; duplicated amount | DB-local |
| C10 | `audit_events` rows deleted or mutated | `aidledger_auditor` | `audit` | Current-state read passes | `[INV-AUDIT-001]` | `BLOCKED` | Missing or altered event ids, with before and after digests | DB-local |
| C11 | `payments` expand, backfill, verify, contract | all | `rls`, `money`, `rolling` | All pass | `case_class: safe` | `READY_FOR_REVIEW` | None; safe control | DB-local |
| C12 | `payments` and `disbursements`, full timeline | all | all seven | All pass | `case_class: safe` | `READY_FOR_REVIEW` | None; **nominated challenging case** per brief | DB-local |

## 4. Sandbox tier finding

**Every one of the twelve cases is database-local.** None mutates cluster-level state: no case
creates a role, alters a server setting, creates a tablespace, or requires a server restart.

Consequences:

- the `world_<id>` template-clone tier serves all twelve cases, which is what makes the
  database-per-world optimisation viable for the whole benchmark;
- the fresh-container tier is reserved for **containment tests** — proving a candidate
  *cannot* create a role or run `ALTER SYSTEM` — and for any future case that needs a restart;
- cluster roles and server settings must be asserted identical before and after every world.
  If that assertion ever fails, a case has escaped its tier and its evidence is void.

C07 needs two concurrent sessions but both live in the same database, so it stays database-local.

## 5. Invariant identifiers

Stable ids referenced by policies, oracles, and certificates.

| Id | Statement |
| --- | --- |
| `INV-RLS-001` | No session may read rows belonging to an organisation other than its own |
| `INV-RLS-002` | Every declared role retains the access the policy grants it |
| `INV-RLS-003` | No declared role gains access the policy does not grant it |
| `INV-MONEY-001` | Minor-unit values are exact; no conversion may change a total |
| `INV-IDEM-001` | An interrupted and resumed backfill neither loses nor duplicates effects |
| `INV-IDEM-002` | A retried disbursement with the same idempotency key settles once |
| `INV-COMPAT-001` | Both application versions preserve declared semantics during rollout |
| `INV-LOCK-001` | No migration statement exceeds the declared lock budget |
| `INV-ROLLBACK-001` | Rollback preserves writes committed after the migration began |
| `INV-AUDIT-001` | Audit events remain present, append-only, attributable, and tenant-scoped |
