# Migration Change Certificate — C08

**BLOCKED**

| | |
| --- | --- |
| Candidate change | Split payment status into a lookup table, with a rollback that restores the old table |
| Decisive invariant | INV-ROLLBACK-001 |
| Required next action | Correct the candidate migration and re-run. |
| Human ruling | none required |

## Confirmed blast radius

Nothing confirmed.

## Replay

```bash
uv run proofbench replay /Users/nonso/code/projects/proofbench/tests/golden/C08/certificate.json
```

---

## Decision

- INV-ROLLBACK-001 failed in world rollback: the declared rollback could not run at all

Decisive checks: rollback:script-runs
Evidence complete: yes
Possible impact (not executed): 0

## Visible tests

- `visible:0:001_status_normalised.sql` — **passed**
## Worlds

### rollback — failed

Threatened invariants: INV-ROLLBACK-001
Checks executed: 1
Semantic digest: `ba2b0b1692c383c165c67e87723982577576a8631667f84f82b6b8ad80fb8ca8`

- **INV-ROLLBACK-001** — the declared rollback could not run at all
  - expected: the rollback executes and restores the previous shape
  - observed: SQLSTATE 23502: null value in column "status_id" of relation "payments" violates not-null constraint

## Trajectory

12 events, root `ac8f44995a65e3e6`.

1. [ingest] reviewing C08: Split payment status into a lookup table, with a rollback that restores the old table
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 1482 chars
4. [contract] No payment is written between the backup being taken and the rollback running.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 633 chars
7. [design-worlds] plan selects rollback
8. [visible-tests] 1/1 visible tests passed
9. [world:rollback] running world rollback on w_c08_rollback
10. [world:rollback] world rollback ended as failed findings=INV-ROLLBACK-001
11. [decide] decision: BLOCKED
12. [complete] C08 -> BLOCKED

## Environment

| | |
| --- | --- |
| Python | 3.12.12 |
| Platform | macOS-14.1-x86_64-i386-64bit |
| PostgreSQL image | `postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94` |
| Resolved image id | `sha256:43064e70a75c153a0ea5abed66b08e2981b7b43088bd59fb4b9f1a20ae4b62b0` |
| Time zone | UTC |

Inputs digest: `ec719c83c3c5dfef43b517f04aa3aa68f20f1e65b84351ebce6f31bb5c8c930f`
Manifest: `manifest.json`

## Known limits

- One world (tenant isolation) is implemented. Money, rolling compatibility, interruption, rollback, lock budget, and audit history are not yet executed, so this certificate says nothing about them.
- No agent participated in this run. The contract, world selection, and any remediation are absent by design at this stage, not omitted by failure.
- Possible impact is empty because it is derived from contract analysis, which is not implemented. Only confirmed impact is reported.
- ProofBench reviews a candidate in a sandbox. It does not approve, merge, or apply a migration, and READY_FOR_REVIEW is not an approval.
