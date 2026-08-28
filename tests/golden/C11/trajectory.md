# Trajectory — C11

Run `C11`. 14 events. Trace root `2b3dfec09013bccf`.

Observable actions only. No hidden reasoning is recorded, and none is
reconstructed here.

## Stages

- `ingest`
- `agent:contract_analyst`
- `contract`
- `agent:test_designer`
- `design-worlds`
- `visible-tests`
- `world:rls`
- `world:money`
- `decide`
- `complete`

## Timeline

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
