# Trajectory — C04

Run `C04`. 12 events. Trace root `1dc6ce538ce5846f`.

Observable actions only. No hidden reasoning is recorded, and none is
reconstructed here.

## Stages

- `ingest`
- `agent:contract_analyst`
- `contract`
- `agent:test_designer`
- `design-worlds`
- `authority`
- `visible-tests`
- `decide`
- `complete`

## Timeline

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
