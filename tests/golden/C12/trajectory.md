# Trajectory — C12

Run `C12`. 24 events. Trace root `ecaf2d0b16a563a9`.

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
- `world:rolling`
- `world:interruption`
- `world:rollback`
- `world:locks`
- `world:audit`
- `decide`
- `complete`

## Timeline

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
