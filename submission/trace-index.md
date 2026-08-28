# Trace index

A representative trajectory for every agent, and how to read it. Required by
hackathon deliverable 04.

Every path below is a committed artifact. Each trajectory validates:

```bash
uv run proofbench trace validate tests/golden/C01/trajectory.jsonl
```

## The one to read first — C01

[`tests/golden/C01/trajectory.md`](../tests/golden/C01/trajectory.md) contains
all three product agents and the sequence the product exists to produce:
**assumption → executed check → failed expectation → correction → verified
result.**

```
 1. [ingest]                   reviewing C01: Recreate payments to add a settlement reference
 2. [agent:contract_analyst]   contract_analyst request, attempt 1
 3. [agent:contract_analyst]   contract_analyst responded, 3219 chars
 4. [contract]                 Recreating a table preserves the row-level security policies
                               that applied to the original table.          <- assumption, uncited
 5. [contract]                 The grants restored by the migration are sufficient to preserve
                               the tenant boundary.
 6. [agent:test_designer]      test_designer request, attempt 1
 8. [design-worlds]            plan selects rls                             <- assumption -> world
 9. [visible-tests]            1/1 visible tests passed                     <- the obvious check is fooled
11. [world:rls]                world rls ended as failed findings=INV-RLS-001  <- expectation fails
13. [agent:remediation_engineer] responded, 3120 chars
14. [remediate]                correction addresses INV-RLS-001
16. [world:rls]                world rls ended as passed                    <- correction verified
17. [decide]                   decision: BLOCKED                            <- about the candidate, not the fix
```

Line 4 is the whole product in one line: the agent could not cite evidence for
the thing the migration depends on, so a world was run to settle it. Line 17 is
the other half: the correction passing does not change the verdict on what was
submitted.

## Per agent

| Agent | Trajectory | Structured output | What to look at |
| --- | --- | --- | --- |
| Contract Analyst | [`C01/trajectory.md`](../tests/golden/C01/trajectory.md) lines 2–5 | [`C01/contract.json`](../tests/golden/C01/contract.json) | Five facts each citing a file and line; two assumptions marked `blocking` with `evidence_checked` listing what was searched and did not settle it |
| Adversarial Test Designer | [`C01/trajectory.md`](../tests/golden/C01/trajectory.md) lines 6–8 | [`C01/world-plan.json`](../tests/golden/C01/world-plan.json) | The plan names the threatened invariants and says why the final schema cannot settle them |
| Remediation Engineer | [`C01/trajectory.md`](../tests/golden/C01/trajectory.md) lines 12–16 | [`C01/remediation.json`](../tests/golden/C01/remediation.json) | The correction, and the clean rerun that verified it rather than the agent's claim |
| Contract Analyst, authority path | [`C04/trajectory.md`](../tests/golden/C04/trajectory.md) | [`C04/contract.json`](../tests/golden/C04/contract.json), [`C04/ruling-packet.md`](../tests/golden/C04/ruling-packet.md) | `authority_questions` with a named reviewer qualification, and the packet built from it |
| Direct reviewer (baseline) | *No trajectory* | — | Implemented but not run; it needs a provider key. See `results/comparison.md` |

## The challenging case — C12

[`tests/golden/C12/trajectory.md`](../tests/golden/C12/trajectory.md) shows the
Test Designer selecting all seven worlds and every one of them passing. It is the
control that makes the other eleven mean something: a system that blocked
whatever it was shown would fail here.

## What is not in a trajectory

No hidden chain-of-thought, on any path. Traces record what was sent, what came
back, which tools ran, what they returned, and what was decided. Concise
agent-authored rationales intended for a reader are included; internal reasoning
is not recorded and therefore cannot be reconstructed.

Credentials and private host paths are redacted **before** hashing, so the chain
never commits to a secret's value. A test asserts a generated password cannot
appear in a trace even when deliberately passed into one
(`tests/unit/test_trace.py::test_secrets_are_redacted_before_they_are_hashed`).
