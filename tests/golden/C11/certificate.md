# Migration Change Certificate — C11

**READY_FOR_REVIEW**

| | |
| --- | --- |
| Candidate change | Add a nullable settlement reference by expand, backfill, verify and contract |
| Decisive invariant | none failed |
| Required next action | A qualified engineer reviews the certificate and the candidate migration. This is not an automatic approval. |
| Human ruling | none required |

## Confirmed blast radius

Nothing confirmed.

## Replay

```bash
uv run proofbench replay tests/golden/C11/certificate.json
```

---

## Decision

- world rls passed
- world money passed

Decisive checks: money:conservation, money:settled-once, rls:app-delete-own, rls:app-select-other, rls:app-select-own, rls:app-update-other, rls:auditor-select-other-audit, rls:auditor-select-own-audit, rls:auditor-select-payments, rls:orgadmin-insert-own, rls:orgadmin-select-other, rls:orgadmin-select-own, rls:service-select-other, rls:service-select-own
Evidence complete: yes
Possible impact (not executed): 0

## Visible tests

- `visible:0:001_reference_backfilled.sql` — **passed**
## Worlds

### rls — passed

Threatened invariants: INV-RLS-001, INV-RLS-002, INV-RLS-003
Checks executed: 12
Semantic digest: `6543938a1f2cf13bd8195967efccf081033ee94892cf9cc4632cc82191269da0`

### money — passed

Threatened invariants: INV-MONEY-001, INV-MONEY-002, INV-IDEM-002
Checks executed: 2
Semantic digest: `52d49068c43c4094fe778a30fbed5720aafa86c9632c00d7dfd7a58612cf83cb`


## Trajectory

14 events, root `5a74efe94a094f5c`.

1. [ingest] reviewing C11: Add a nullable settlement reference by expand, backfill, verify and contract
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 1747 chars
4. [contract] Adding a nullable column without a default does not rewrite the table.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 821 chars
7. [design-worlds] plan selects rls, money
8. [visible-tests] 1/1 visible tests passed
9. [world:rls] running world rls on w_c11_rls
10. [world:rls] world rls ended as passed
11. [world:money] running world money on w_c11_money
12. [world:money] world money ended as passed
13. [decide] decision: READY_FOR_REVIEW
14. [complete] C11 -> READY_FOR_REVIEW

## Environment

| | |
| --- | --- |
| Python | 3.12.12 |
| Platform | macOS-14.1-x86_64-i386-64bit |
| PostgreSQL image | `postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94` |
| Resolved image id | `sha256:43064e70a75c153a0ea5abed66b08e2981b7b43088bd59fb4b9f1a20ae4b62b0` |
| Time zone | UTC |

Inputs digest: `563c29a8159385b9a2525d66d6e6fe0706e9fb98392dd87f76e1e365e7020ae6`
Manifest: `manifest.json`

## Known limits

- One world (tenant isolation) is implemented. Money, rolling compatibility, interruption, rollback, lock budget, and audit history are not yet executed, so this certificate says nothing about them.
- No agent participated in this run. The contract, world selection, and any remediation are absent by design at this stage, not omitted by failure.
- Possible impact is empty because it is derived from contract analysis, which is not implemented. Only confirmed impact is reported.
- ProofBench reviews a candidate in a sandbox. It does not approve, merge, or apply a migration, and READY_FOR_REVIEW is not an approval.
