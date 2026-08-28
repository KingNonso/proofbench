# Trajectory — C02

Run `C02`. 12 events. Trace root `b0c2a2f239fc1255`.

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
- `decide`
- `complete`

## Timeline

1. [ingest] reviewing C02: Restore payments policies for the application role only
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 2150 chars
4. [contract] Restoring the policy the application uses is sufficient to restore the tenant boundary for every declared role.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 661 chars
7. [design-worlds] plan selects rls
8. [visible-tests] 1/1 visible tests passed
9. [world:rls] running world rls on w_c02_rls
10. [world:rls] world rls ended as failed findings=INV-RLS-002
11. [decide] decision: BLOCKED
12. [complete] C02 -> BLOCKED
