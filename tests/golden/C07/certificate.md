# Migration Change Certificate — C07

**BLOCKED**

| | |
| --- | --- |
| Candidate change | Rewrite payments to add a non-null column with a volatile default |
| Decisive invariant | INV-LOCK-001 |
| Required next action | Correct the candidate migration and re-run. |
| Human ruling | none required |

## Confirmed blast radius

Nothing confirmed.

## Replay

```bash
uv run proofbench replay tests/golden/C07/certificate.json
```

---

## Decision

- INV-LOCK-001 failed in world locks: the statement rewrites payments, holding ACCESS EXCLUSIVE for the whole rewrite

Decisive checks: locks:no-table-rewrite
Evidence complete: yes
Possible impact (not executed): 0

## Visible tests

- `visible:0:001_token_present.sql` — **passed**
## Worlds

### locks — failed

Threatened invariants: INV-LOCK-001
Checks executed: 2
Semantic digest: `276ad6e0e3658a2b3b0ea1a619bcdf53d3cf723827fab560c74f27ff0a63dfb0`

- **INV-LOCK-001** — the statement rewrites payments, holding ACCESS EXCLUSIVE for the whole rewrite
  - expected: a metadata-only change that takes its lock and returns
  - observed: relation filenode changed from 16414 to 16511

## Trajectory

12 events, root `0be28d9f3e741188`.

1. [ingest] reviewing C07: Rewrite payments to add a non-null column with a volatile default
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 1360 chars
4. [contract] Adding a column with a default is a metadata-only operation on this table.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 640 chars
7. [design-worlds] plan selects locks
8. [visible-tests] 1/1 visible tests passed
9. [world:locks] running world locks on w_c07_locks-clean
10. [world:locks] world locks ended as failed findings=INV-LOCK-001
11. [decide] decision: BLOCKED
12. [complete] C07 -> BLOCKED

## Environment

| | |
| --- | --- |
| Python | 3.12.12 |
| Platform | macOS-14.1-x86_64-i386-64bit |
| PostgreSQL image | `postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94` |
| Resolved image id | `sha256:43064e70a75c153a0ea5abed66b08e2981b7b43088bd59fb4b9f1a20ae4b62b0` |
| Time zone | UTC |

Inputs digest: `2549256bf74f661aa677b8a648c46cf8a17d782b4cf90c391b0035dc5501a19c`
Manifest: `manifest.json`

## Known limits

- One world (tenant isolation) is implemented. Money, rolling compatibility, interruption, rollback, lock budget, and audit history are not yet executed, so this certificate says nothing about them.
- No agent participated in this run. The contract, world selection, and any remediation are absent by design at this stage, not omitted by failure.
- Possible impact is empty because it is derived from contract analysis, which is not implemented. Only confirmed impact is reported.
- ProofBench reviews a candidate in a sandbox. It does not approve, merge, or apply a migration, and READY_FOR_REVIEW is not an approval.
