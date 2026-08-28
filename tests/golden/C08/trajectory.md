# Trajectory — C08

Run `C08`. 12 events. Trace root `ac8f44995a65e3e6`.

Observable actions only. No hidden reasoning is recorded, and none is
reconstructed here.

## Stages

- `ingest`
- `agent:contract_analyst`
- `contract`
- `agent:test_designer`
- `design-worlds`
- `visible-tests`
- `world:rollback`
- `decide`
- `complete`

## Timeline

1. [ingest] reviewing C08: Split payment status into a lookup table, with a rollback that restores the old table
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 1482 chars
4. [contract] No payment is written between the backup being taken and the rollback running.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 633 chars
7. [design-worlds] plan selects rollback
8. [visible-tests] 1/1 visible tests passed
9. [world:rollback] running world rollback on w_c08_rollback
10. [world:rollback] world rollback ended as failed findings=INV-ROLLBACK-001
11. [decide] decision: BLOCKED
12. [complete] C08 -> BLOCKED
