# Migration Change Certificate — C03

**BLOCKED**

| | |
| --- | --- |
| Candidate change | Re-denominate payment amounts through a floating point conversion |
| Decisive invariant | INV-MONEY-001 |
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

- INV-MONEY-001 failed in world money: 4 payment amount(s) changed during the migration

Decisive checks: money:conservation
Evidence complete: yes
Possible impact (not executed): 0

## Visible tests

- `visible:0:001_amounts_are_integers.sql` — **passed**
## Worlds

### money — failed

Threatened invariants: INV-MONEY-001, INV-MONEY-002, INV-IDEM-002
Checks executed: 2
Semantic digest: `a1b9bc4c4f068303fc14ea98bae166441a57eb93c62f710a7710b46d60b4706b`

- **INV-MONEY-001** — 4 payment amount(s) changed during the migration
  - expected: every amount_minor unchanged
  - observed: changed: ccccccc3-0000-4000-8000-000000000001, ccccccc3-0000-4000-8000-000000000003, ddddddd4-0000-4000-8000-000000000001, ddddddd4-0000-4000-8000-000000000002

## Trajectory

12 events, root `7238809bce203ee1`.

1. [ingest] reviewing C03: Re-denominate payment amounts through a floating point conversion
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 1494 chars
4. [contract] A double-precision multiplication followed by a cast preserves the intended value for every affected row.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 603 chars
7. [design-worlds] plan selects money
8. [visible-tests] 1/1 visible tests passed
9. [world:money] running world money on w_c03_money
10. [world:money] world money ended as failed findings=INV-MONEY-001
11. [decide] decision: BLOCKED
12. [complete] C03 -> BLOCKED

## Environment

| | |
| --- | --- |
| Python | 3.12.12 |
| Platform | macOS-14.1-x86_64-i386-64bit |
| PostgreSQL image | `postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94` |
| Resolved image id | `sha256:43064e70a75c153a0ea5abed66b08e2981b7b43088bd59fb4b9f1a20ae4b62b0` |
| Time zone | UTC |

Inputs digest: `564699bc75e2516301c2f85c3f13fcc62e6737f2de16a20c2778a6bfffd0e01d`
Manifest: `manifest.json`

## Known limits

- World evidence is limited to the checks selected and executed for this case: money.
- No hypothetical blast-radius findings were recorded. Only impacts supported by executed evidence appear as confirmed impact.
- ProofBench reviews a candidate in a sandbox. It does not approve, merge, or apply a migration, and READY_FOR_REVIEW is not an approval.
