# Migration Change Certificate — C09

**BLOCKED**

| | |
| --- | --- |
| Candidate change | Settle approved payments through a retried dual-write path |
| Decisive invariant | INV-IDEM-002 |
| Required next action | Correct the candidate migration and re-run. |
| Human ruling | none required |

## Confirmed blast radius

Nothing confirmed.

## Replay

```bash
uv run proofbench replay tests/golden/C09/certificate.json
```

---

## Decision

- INV-IDEM-002 failed in world money: 1 payment(s) were settled more than once by the migration

Decisive checks: money:settled-once
Evidence complete: yes
Possible impact (not executed): 0

## Visible tests

- `visible:0:001_approved_are_settled.sql` — **passed**
## Worlds

### money — failed

Threatened invariants: INV-MONEY-001, INV-MONEY-002, INV-IDEM-002
Checks executed: 2
Semantic digest: `f4db7f772c4488f3ef275cec345846f34fff23e53c11c5b28a9444f357b05abc`

- **INV-IDEM-002** — 1 payment(s) were settled more than once by the migration
  - expected: each payment settles exactly once
  - observed: duplicated: ccccccc3-0000-4000-8000-000000000002

## Trajectory

12 events, root `38b64cc40a68608d`.

1. [ingest] reviewing C09: Settle approved payments through a retried dual-write path
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 2034 chars
4. [contract] The unique constraint on the idempotency key prevents a payment from being settled twice.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 641 chars
7. [design-worlds] plan selects money
8. [visible-tests] 1/1 visible tests passed
9. [world:money] running world money on w_c09_money
10. [world:money] world money ended as failed findings=INV-IDEM-002
11. [decide] decision: BLOCKED
12. [complete] C09 -> BLOCKED

## Environment

| | |
| --- | --- |
| Python | 3.12.12 |
| Platform | macOS-14.1-x86_64-i386-64bit |
| PostgreSQL image | `postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94` |
| Resolved image id | `sha256:43064e70a75c153a0ea5abed66b08e2981b7b43088bd59fb4b9f1a20ae4b62b0` |
| Time zone | UTC |

Inputs digest: `f4220267f9db7ed3947b410dda6103ff847ed5befd0a0bd13ef364bc6e5351ca`
Manifest: `manifest.json`

## Known limits

- One world (tenant isolation) is implemented. Money, rolling compatibility, interruption, rollback, lock budget, and audit history are not yet executed, so this certificate says nothing about them.
- No agent participated in this run. The contract, world selection, and any remediation are absent by design at this stage, not omitted by failure.
- Possible impact is empty because it is derived from contract analysis, which is not implemented. Only confirmed impact is reported.
- ProofBench reviews a candidate in a sandbox. It does not approve, merge, or apply a migration, and READY_FOR_REVIEW is not an approval.
