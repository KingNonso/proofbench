# Migration Change Certificate — C01

**BLOCKED**

| | |
| --- | --- |
| Candidate change | Recreate payments to add a settlement reference |
| Decisive invariant | INV-RLS-001 |
| Required next action | Correct the candidate migration and re-run. |
| Human ruling | none required |

## Confirmed blast radius

Derived from executed evidence only.

| Invariant | Role | Operation | Affected tenant | Rows | Evidence |
| --- | --- | --- | --- | ---: | --- |
| INV-RLS-001 | `aidledger_app` | SELECT | `22222222-2222-4222-8222-222222222222` | 2 | rls:app-select-other |
| INV-RLS-001 | `aidledger_app` | UPDATE | `22222222-2222-4222-8222-222222222222` | 2 | rls:app-update-other |
| INV-RLS-001 | `aidledger_org_admin` | SELECT | `11111111-1111-4111-8111-111111111111` | 3 | rls:orgadmin-select-other |
| INV-RLS-001 | `aidledger_service` | SELECT | `22222222-2222-4222-8222-222222222222` | 2 | rls:service-select-other |

## Replay

```bash
uv run proofbench replay tests/golden/C01/certificate.json
```

---

## Decision

- INV-RLS-001 failed in world rls: aidledger_app reached 2 payments row(s) belonging to organisation 22222222-2222-4222-8222-222222222222 and 1 other tenant(s)

Decisive checks: rls:app-select-other, rls:app-update-other, rls:orgadmin-select-other, rls:service-select-other
Evidence complete: yes
Possible impact (not executed): 0

## Visible tests

- `visible:0:001_schema_shape.sql` — **passed**
## Proposed correction

A correction was proposed after the candidate was blocked. It does **not** change
the decision above, which is about the candidate as submitted.

| | |
| --- | --- |
| Addresses | INV-RLS-001 |
| Verified by clean rerun | yes |
| Regression check | settlement_reference still exists, all five payments survive, the disbursements foreign key is intact, and every tenant-isolation probe passes. |

Row-level security is an attribute of the table, so the rewrite discarded ENABLE, FORCE and every policy on payments. The correction keeps the table rewrite and the new column, and re-declares the security attributes and the three policies that applied before. Nothing else changes.

## Worlds

### rls — failed

Threatened invariants: INV-RLS-001, INV-RLS-002, INV-RLS-003
Checks executed: 12
Semantic digest: `1beb7ffe586dd1747a21ab945c84202471501dfa5544c4a789fc1b635fec20c0`

- **INV-RLS-001** — aidledger_app reached 2 payments row(s) belonging to organisation 22222222-2222-4222-8222-222222222222 and 1 other tenant(s)
  - expected: app-select-other: deny_empty; app-update-other: deny_empty; orgadmin-select-other: deny_empty; service-select-other: deny_empty
  - observed: app-select-other: 2 row(s); app-update-other: 2 row(s); orgadmin-select-other: 3 row(s); service-select-other: 2 row(s)

## Trajectory

18 events, root `932c77e26ccc4770`.

1. [ingest] reviewing C01: Recreate payments to add a settlement reference
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 3219 chars
4. [contract] Recreating a table preserves the row-level security policies that applied to the original table.
5. [contract] The grants restored by the migration are sufficient to preserve the tenant boundary.
6. [agent:test_designer] test_designer request, attempt 1
7. [agent:test_designer] test_designer responded, 809 chars
8. [design-worlds] plan selects rls
9. [visible-tests] 1/1 visible tests passed
10. [world:rls] running world rls on w_c01_rls
11. [world:rls] world rls ended as failed findings=INV-RLS-001
12. [agent:remediation_engineer] remediation_engineer request, attempt 1
13. [agent:remediation_engineer] remediation_engineer responded, 3120 chars
14. [remediate] correction addresses INV-RLS-001
15. [world:rls] running world rls on w_c01_rls-corrected
16. [world:rls] world rls ended as passed
17. [decide] decision: BLOCKED
18. [complete] C01 -> BLOCKED

## Environment

| | |
| --- | --- |
| Python | 3.12.12 |
| Platform | macOS-14.1-x86_64-i386-64bit |
| PostgreSQL image | `postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94` |
| Resolved image id | `sha256:43064e70a75c153a0ea5abed66b08e2981b7b43088bd59fb4b9f1a20ae4b62b0` |
| Time zone | UTC |

Inputs digest: `6d9c33ec0c8be2a784f75a81180075e457c1e2ed4fb78c199aabd0731b1eef4d`
Manifest: `manifest.json`

## Known limits

- One world (tenant isolation) is implemented. Money, rolling compatibility, interruption, rollback, lock budget, and audit history are not yet executed, so this certificate says nothing about them.
- No agent participated in this run. The contract, world selection, and any remediation are absent by design at this stage, not omitted by failure.
- Possible impact is empty because it is derived from contract analysis, which is not implemented. Only confirmed impact is reported.
- ProofBench reviews a candidate in a sandbox. It does not approve, merge, or apply a migration, and READY_FOR_REVIEW is not an approval.
