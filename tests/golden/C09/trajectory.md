# Trajectory — C09

Run `C09`. 12 events. Trace root `88283306877d69be`.

Observable actions only. No hidden reasoning is recorded, and none is
reconstructed here.

## Stages

- `ingest`
- `agent:contract_analyst`
- `contract`
- `agent:test_designer`
- `design-worlds`
- `visible-tests`
- `world:money`
- `decide`
- `complete`

## Timeline

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
