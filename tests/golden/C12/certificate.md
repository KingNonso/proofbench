# Migration Change Certificate — C12

**READY_FOR_REVIEW**

| | |
| --- | --- |
| Candidate change | Introduce a reconciliation column across a rolling deploy, with a safe rollback |
| Decisive invariant | none failed |
| Required next action | A qualified engineer reviews the certificate and the candidate migration. This is not an automatic approval. |
| Human ruling | none required |

## Confirmed blast radius

Nothing confirmed.

## Replay

```bash
uv run proofbench replay certificate.json
```

---

## Decision

- world rls passed
- world money passed
- world rolling passed
- world interruption passed
- world rollback passed
- world locks passed
- world audit passed

Decisive checks: audit:events-still-present, audit:events-unaltered, interruption:resume-is-a-no-op, locks:no-table-rewrite, locks:within-budget, money:conservation, money:settled-once, rls:app-delete-own, rls:app-select-other, rls:app-select-own, rls:app-update-other, rls:auditor-select-other-audit, rls:auditor-select-own-audit, rls:auditor-select-payments, rls:orgadmin-insert-own, rls:orgadmin-select-other, rls:orgadmin-select-own, rls:service-select-other, rls:service-select-own, rollback:post-start-write-survives, rolling:v1:read the columns v1 knows, rolling:v1:record a payment the v1 way, rolling:v2:read the new column, rolling:v2:record a payment the v2 way
Evidence complete: yes
Possible impact (not executed): 0

## Visible tests

- `visible:0:001_reconciliation_key.sql` — **passed**
## Worlds

### rls — passed

Threatened invariants: INV-RLS-001, INV-RLS-002, INV-RLS-003
Checks executed: 12
Semantic digest: `6543938a1f2cf13bd8195967efccf081033ee94892cf9cc4632cc82191269da0`

### money — passed

Threatened invariants: INV-MONEY-001, INV-MONEY-002, INV-IDEM-002
Checks executed: 2
Semantic digest: `52d49068c43c4094fe778a30fbed5720aafa86c9632c00d7dfd7a58612cf83cb`

### rolling — passed

Threatened invariants: INV-COMPAT-001
Checks executed: 4
Semantic digest: `d3dbc4775a4d78b81a67ac82ade3dc9f6ccc820f4c6426b157e3bff98a25fc77`

### interruption — passed

Threatened invariants: INV-IDEM-001
Checks executed: 1
Semantic digest: `a058c1c388f38c7b469afe660c28d754f7909d6797a2a793a7956f29d4f154f5`

### rollback — passed

Threatened invariants: INV-ROLLBACK-001
Checks executed: 1
Semantic digest: `4c25a330bdcc4ede66b205d9a5c42c9b766ce50db9478a104a638cf72b6277b2`

### locks — passed

Threatened invariants: INV-LOCK-001
Checks executed: 2
Semantic digest: `385d73f10b512bdc2fd9ade07fa0de2cf556ad4a63b5284d98387142bf546e4c`

### audit — passed

Threatened invariants: INV-AUDIT-001
Checks executed: 2
Semantic digest: `97d5002f381ebb2f1aca86fb5084ecb00d7b525e2a44266fad34927b87631998`


## Trajectory

24 events, root `2b2112fdeee3625a`.

1. [ingest] reviewing C12: Introduce a reconciliation column across a rolling deploy, with a safe rollback
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 3692 chars
4. [contract] A deterministic backfill key derived from the row makes a resumed backfill a no-op.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 2218 chars
7. [design-worlds] plan selects rls, money, rolling, interruption, rollback, locks, audit
8. [visible-tests] 1/1 visible tests passed
9. [world:rls] running world rls on w_c12_rls
10. [world:rls] world rls ended as passed
11. [world:money] running world money on w_c12_money
12. [world:money] world money ended as passed
13. [world:rolling] running world rolling on w_c12_rolling
14. [world:rolling] world rolling ended as passed
15. [world:interruption] running world interruption on w_c12_interruption
16. [world:interruption] world interruption ended as passed
17. [world:rollback] running world rollback on w_c12_rollback
18. [world:rollback] world rollback ended as passed
19. [world:locks] running world locks on w_c12_locks-clean
20. [world:locks] world locks ended as passed
21. [world:audit] running world audit on w_c12_audit
22. [world:audit] world audit ended as passed
23. [decide] decision: READY_FOR_REVIEW
24. [complete] C12 -> READY_FOR_REVIEW

## Environment

| | |
| --- | --- |
| Python | 3.12.12 |
| Platform | macOS-14.1-x86_64-i386-64bit |
| PostgreSQL image | `postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94` |
| Resolved image id | `sha256:43064e70a75c153a0ea5abed66b08e2981b7b43088bd59fb4b9f1a20ae4b62b0` |
| Time zone | UTC |

Inputs digest: `06d41d56c491b2fa1a61b6443d95d388fbe456672e2971e29930c6399cd2979a`
Manifest: `manifest.json`

## Known limits

- World evidence is limited to the checks selected and executed for this case: audit, interruption, locks, money, rls, rollback, rolling.
- No hypothetical blast-radius findings were recorded. Only impacts supported by executed evidence appear as confirmed impact.
- ProofBench reviews a candidate in a sandbox. It does not approve, merge, or apply a migration, and READY_FOR_REVIEW is not an approval.
