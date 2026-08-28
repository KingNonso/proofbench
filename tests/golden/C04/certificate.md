# Migration Change Certificate — C04

**DOMAIN_RULING_REQUIRED**

| | |
| --- | --- |
| Candidate change | Backfill a missing currency and make the column NOT NULL |
| Decisive invariant | none failed |
| Required next action | A qualified domain owner records a scoped ruling on the open question. |
| Human ruling | none required |

## Confirmed blast radius

Nothing confirmed.

## Replay

```bash
uv run proofbench replay /Users/nonso/code/projects/proofbench/tests/golden/C04/certificate.json
```

---

## Decision

- unresolved authority question: Were all payments recorded before the currency field existed denominated in USD, or must their currency be sourced per organisation?

Decisive checks: none
Evidence complete: yes
Possible impact (not executed): 0

## Visible tests

- `visible:0:001_currency_not_null.sql` — **passed**
## Worlds


## Trajectory

12 events, root `e0592e54a1c8e3ad`.

1. [ingest] reviewing C04: Backfill a missing currency and make the column NOT NULL
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 3462 chars
4. [contract] Every payment recorded before the currency field existed was denominated in USD.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 1171 chars
7. [design-worlds] plan selects money, rls
8. [authority] authority required: Were all payments recorded before the currency field existed denominated in USD, or must their currency be sourced per organisation?
9. [visible-tests] 1/1 visible tests passed
10. [authority] worlds deferred pending a domain ruling
11. [decide] decision: DOMAIN_RULING_REQUIRED
12. [complete] C04 -> DOMAIN_RULING_REQUIRED

## Environment

| | |
| --- | --- |
| Python | 3.12.12 |
| Platform | macOS-14.1-x86_64-i386-64bit |
| PostgreSQL image | `postgres:16@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94` |
| Resolved image id | `sha256:43064e70a75c153a0ea5abed66b08e2981b7b43088bd59fb4b9f1a20ae4b62b0` |
| Time zone | UTC |

Inputs digest: `4f5535e95ebcf4ead024930dccfedc1f6f78e524eedccf0714cee03e671b200f`
Manifest: `manifest.json`

## Known limits

- One world (tenant isolation) is implemented. Money, rolling compatibility, interruption, rollback, lock budget, and audit history are not yet executed, so this certificate says nothing about them.
- No agent participated in this run. The contract, world selection, and any remediation are absent by design at this stage, not omitted by failure.
- Possible impact is empty because it is derived from contract analysis, which is not implemented. Only confirmed impact is reported.
- ProofBench reviews a candidate in a sandbox. It does not approve, merge, or apply a migration, and READY_FOR_REVIEW is not an approval.
