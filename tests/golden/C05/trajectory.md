# Trajectory — C05

Run `C05`. 12 events. Trace root `6df7d2fb4923f202`.

Observable actions only. No hidden reasoning is recorded, and none is
reconstructed here.

## Stages

- `ingest`
- `agent:contract_analyst`
- `contract`
- `agent:test_designer`
- `design-worlds`
- `visible-tests`
- `world:rolling`
- `decide`
- `complete`

## Timeline

1. [ingest] reviewing C05: Drop the old amount column after adding a scaled replacement
2. [agent:contract_analyst] contract_analyst request, attempt 1
3. [agent:contract_analyst] contract_analyst responded, 1426 chars
4. [contract] Every application instance writing amount_minor has been replaced before this migration runs.
5. [agent:test_designer] test_designer request, attempt 1
6. [agent:test_designer] test_designer responded, 658 chars
7. [design-worlds] plan selects rolling
8. [visible-tests] 1/1 visible tests passed
9. [world:rolling] running world rolling on w_c05_rolling
10. [world:rolling] world rolling ended as failed findings=INV-COMPAT-001
11. [decide] decision: BLOCKED
12. [complete] C05 -> BLOCKED
