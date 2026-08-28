# Migration Change Certificate — C10

**BLOCKED**

| | |
| --- | --- |
| Candidate change | Compact audit history while adding a retention column |
| Decisive invariant | INV-AUDIT-001 |
| Required next action | Correct the candidate migration and re-run. |
| Human ruling | none required |

## Confirmed blast radius

Nothing confirmed.

## Replay

```bash
uv run proofbench replay tests/golden/C10/certificate.json
```

---

## Decision

- INV-AUDIT-001 failed in world audit: the migration changed audit history

Decisive checks: audit:events-still-present, audit:events-unaltered
Evidence complete: yes
Possible impact (not executed): 0

## Visible tests

- `visible:0:001_retention_present.sql` — **passed**
## Worlds

### audit — failed

Threatened invariants: INV-AUDIT-001
Checks executed: 2
Semantic digest: `bf348411eefee157117d363ade30e08d301b13baa219b1a67494ea06ba6aa717`

- **INV-AUDIT-001** — the migration changed audit history
  - expected: audit events are append-only; nothing is removed or rewritten
  - observed: 2 event(s) removed: [2, 4]

## Trajectory

12 events, root `622ccfdb2360d64c`.

1. [ingest] reviewing C10: Compact audit history while adding a retention column
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 1398 chars
4. [contract] The deleted audit events are redundant and are not required by any reader.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 581 chars
7. [design-worlds] plan selects audit
8. [visible-tests] 1/1 visible tests passed
9. [world:audit] running world audit on w_c10_audit
10. [world:audit] world audit ended as failed findings=INV-AUDIT-001
11. [decide] decision: BLOCKED
12. [complete] C10 -> BLOCKED

## Environment

| | |
| --- | --- |
| Python | 3.12.12 |
| Platform | macOS-14.1-x86_64-i386-64bit |
| PostgreSQL image | `postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94` |
| Resolved image id | `sha256:43064e70a75c153a0ea5abed66b08e2981b7b43088bd59fb4b9f1a20ae4b62b0` |
| Time zone | UTC |

Inputs digest: `e58a4fc2b7044825ec2f69b394f61694855af2fb2597923db119853662a4879e`
Manifest: `manifest.json`

## Known limits

- One world (tenant isolation) is implemented. Money, rolling compatibility, interruption, rollback, lock budget, and audit history are not yet executed, so this certificate says nothing about them.
- No agent participated in this run. The contract, world selection, and any remediation are absent by design at this stage, not omitted by failure.
- Possible impact is empty because it is derived from contract analysis, which is not implemented. Only confirmed impact is reported.
- ProofBench reviews a candidate in a sandbox. It does not approve, merge, or apply a migration, and READY_FOR_REVIEW is not an approval.
