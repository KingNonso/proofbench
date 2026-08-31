# Migration Change Certificate — C05

**BLOCKED**

| | |
| --- | --- |
| Candidate change | Drop the old amount column after adding a scaled replacement |
| Decisive invariant | INV-COMPAT-001 |
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

- INV-COMPAT-001 failed in world rolling: 2 statement(s) a live application version issues no longer work against the migrated schema

Decisive checks: rolling:v1:read payments, rolling:v1:record a payment
Evidence complete: yes
Possible impact (not executed): 0

## Visible tests

- `visible:0:001_new_column_present.sql` — **passed**
## Worlds

### rolling — failed

Threatened invariants: INV-COMPAT-001
Checks executed: 3
Semantic digest: `585cddb88b1687a011fbe6296e87949b7eaf5bd261b4af67e326f8cad8476efe`

- **INV-COMPAT-001** — 2 statement(s) a live application version issues no longer work against the migrated schema
  - expected: both versions keep working throughout the rollout
  - observed: v1/read payments (42703); v1/record a payment (42703)

## Trajectory

12 events, root `9ed1af87bdec8bfd`.

1. [ingest] reviewing C05: Drop the old amount column after adding a scaled replacement
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 1426 chars
4. [contract] Every application instance writing amount_minor has been replaced before this migration runs.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 658 chars
7. [design-worlds] plan selects rolling
8. [visible-tests] 1/1 visible tests passed
9. [world:rolling] running world rolling on w_c05_rolling
10. [world:rolling] world rolling ended as failed findings=INV-COMPAT-001
11. [decide] decision: BLOCKED
12. [complete] C05 -> BLOCKED

## Environment

| | |
| --- | --- |
| Python | 3.12.12 |
| Platform | macOS-14.1-x86_64-i386-64bit |
| PostgreSQL image | `postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94` |
| Resolved image id | `sha256:43064e70a75c153a0ea5abed66b08e2981b7b43088bd59fb4b9f1a20ae4b62b0` |
| Time zone | UTC |

Inputs digest: `ea3d229f84fb0fcac353770c38f7e6584f55fec1ffaeee92a0b38006b1f1599a`
Manifest: `manifest.json`

## Known limits

- World evidence is limited to the checks selected and executed for this case: rolling.
- No hypothetical blast-radius findings were recorded. Only impacts supported by executed evidence appear as confirmed impact.
- ProofBench reviews a candidate in a sandbox. It does not approve, merge, or apply a migration, and READY_FOR_REVIEW is not an approval.
