# Migration Change Certificate — C02

**BLOCKED**

| | |
| --- | --- |
| Candidate change | Restore payments policies for the application role only |
| Decisive invariant | INV-RLS-002 |
| Required next action | Correct the candidate migration and re-run. |
| Human ruling | none required |

## Confirmed blast radius

Nothing confirmed.

## Replay

```bash
uv run proofbench replay tests/golden/C02/certificate.json
```

---

## Decision

- INV-RLS-002 failed in world rls: aidledger_org_admin lost required SELECT access to payments

Decisive checks: rls:orgadmin-select-own
Evidence complete: yes
Possible impact (not executed): 0

## Visible tests

- `visible:0:001_schema_and_rls.sql` — **passed**
## Worlds

### rls — failed

Threatened invariants: INV-RLS-001, INV-RLS-002, INV-RLS-003
Checks executed: 12
Semantic digest: `d215c3f3718d8bead4559011fbb5b838b01cfba92bc86765fcb5b6b30982c6dc`

- **INV-RLS-002** — aidledger_org_admin lost required SELECT access to payments
  - expected: orgadmin-select-own: allow
  - observed: orgadmin-select-own: 0 row(s)

## Trajectory

12 events, root `4fccbcfa7415e70e`.

1. [ingest] reviewing C02: Restore payments policies for the application role only
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 2150 chars
4. [contract] Restoring the policy the application uses is sufficient to restore the tenant boundary for every declared role.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 661 chars
7. [design-worlds] plan selects rls
8. [visible-tests] 1/1 visible tests passed
9. [world:rls] running world rls on w_c02_rls
10. [world:rls] world rls ended as failed findings=INV-RLS-002
11. [decide] decision: BLOCKED
12. [complete] C02 -> BLOCKED

## Environment

| | |
| --- | --- |
| Python | 3.12.12 |
| Platform | macOS-14.1-x86_64-i386-64bit |
| PostgreSQL image | `postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94` |
| Resolved image id | `sha256:43064e70a75c153a0ea5abed66b08e2981b7b43088bd59fb4b9f1a20ae4b62b0` |
| Time zone | UTC |

Inputs digest: `280b85ae91e89c8ce088dac3c12c99feb3af2400b61d9feee1da6e26b707c837`
Manifest: `manifest.json`

## Known limits

- One world (tenant isolation) is implemented. Money, rolling compatibility, interruption, rollback, lock budget, and audit history are not yet executed, so this certificate says nothing about them.
- No agent participated in this run. The contract, world selection, and any remediation are absent by design at this stage, not omitted by failure.
- Possible impact is empty because it is derived from contract analysis, which is not implemented. Only confirmed impact is reported.
- ProofBench reviews a candidate in a sandbox. It does not approve, merge, or apply a migration, and READY_FOR_REVIEW is not an approval.
