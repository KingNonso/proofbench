# Migration Change Certificate — C06

**BLOCKED**

| | |
| --- | --- |
| Candidate change | Backfill disbursements for settled payments without recording progress |
| Decisive invariant | INV-IDEM-001 |
| Required next action | Correct the candidate migration and re-run. |
| Human ruling | none required |

## Confirmed blast radius

Nothing confirmed.

## Replay

```bash
uv run proofbench replay certificate.json
```

---

## Decision

- INV-IDEM-001 failed in world interruption: resuming the backfill changed disbursements: 6 row(s) became 10

Decisive checks: interruption:resume-is-a-no-op
Evidence complete: yes
Possible impact (not executed): 0

## Visible tests

- `visible:0:001_settled_have_disbursements.sql` — **passed**
## Worlds

### interruption — failed

Threatened invariants: INV-IDEM-001
Checks executed: 1
Semantic digest: `a7e2cd3cfed9ecae040457091b905ec7e6c4dc9d4afc517b40d0528bdc8a39a8`

- **INV-IDEM-001** — resuming the backfill changed disbursements: 6 row(s) became 10
  - expected: a resumed backfill leaves the observable state unchanged
  - observed: 4 row(s) added or altered on the retry

## Trajectory

12 events, root `dfbc2c5cbcf9cc2b`.

1. [ingest] reviewing C06: Backfill disbursements for settled payments without recording progress
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 1595 chars
4. [contract] The backfill will run exactly once and will not be interrupted.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 591 chars
7. [design-worlds] plan selects interruption
8. [visible-tests] 1/1 visible tests passed
9. [world:interruption] running world interruption on w_c06_interruption
10. [world:interruption] world interruption ended as failed findings=INV-IDEM-001
11. [decide] decision: BLOCKED
12. [complete] C06 -> BLOCKED

## Environment

| | |
| --- | --- |
| Python | 3.12.12 |
| Platform | macOS-14.1-x86_64-i386-64bit |
| PostgreSQL image | `postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94` |
| Resolved image id | `sha256:43064e70a75c153a0ea5abed66b08e2981b7b43088bd59fb4b9f1a20ae4b62b0` |
| Time zone | UTC |

Inputs digest: `c439f959e34672402428288ca385baa5d64a36a523b5f21c4a63599b62255fe5`
Manifest: `manifest.json`

## Known limits

- World evidence is limited to the checks selected and executed for this case: interruption.
- No hypothetical blast-radius findings were recorded. Only impacts supported by executed evidence appear as confirmed impact.
- ProofBench reviews a candidate in a sandbox. It does not approve, merge, or apply a migration, and READY_FOR_REVIEW is not an approval.
