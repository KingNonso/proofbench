# Trajectory — C07

Run `C07`. 12 events. Trace root `938de759edc2adf1`.

Observable actions only. No hidden reasoning is recorded, and none is
reconstructed here.

## Stages

- `ingest`
- `agent:contract_analyst`
- `contract`
- `agent:test_designer`
- `design-worlds`
- `visible-tests`
- `world:locks`
- `decide`
- `complete`

## Timeline

1. [ingest] reviewing C07: Rewrite payments to add a non-null column with a volatile default
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 1360 chars
4. [contract] Adding a column with a default is a metadata-only operation on this table.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 640 chars
7. [design-worlds] plan selects locks
8. [visible-tests] 1/1 visible tests passed
9. [world:locks] running world locks on w_c07_locks-clean
10. [world:locks] world locks ended as failed findings=INV-LOCK-001
11. [decide] decision: BLOCKED
12. [complete] C07 -> BLOCKED
