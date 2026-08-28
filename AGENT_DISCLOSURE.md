# Agent disclosure

Every agent this project runs, what it can reach, what it cannot decide, and
where to read a real trajectory. Required by hackathon deliverable 04.

Not to be confused with [`AGENTS.md`](AGENTS.md), which is the engineering
standard for AI assistance used to *build* this repository. This file documents
the agents the *product* runs.

## The boundary that matters

**No agent can decide anything.** That is enforced by the schemas rather than by
instruction:

| Agent output | Field it does not have |
| --- | --- |
| `MigrationContract` | any verdict, state, or "is it safe" field |
| `WorldPlan` | any field that could carry a command, SQL, or a path |
| `RemediationPlan` | any field claiming the correction worked |

The external state comes from `decision.policy.decide()`, a pure function over
typed evidence. Agent text is not an input to it, so no amount of confident prose
can turn a failed deterministic check into a pass.

A test asserts each of those absences
(`tests/unit/test_agent_boundaries.py`).

## The three product agents

| Agent | Job | Instructions | May call | May never |
| --- | --- | --- | --- | --- |
| **Contract Analyst** | Separate what the evidence supports from what it does not; raise an authority question when a business fact cannot be derived | [`contract_analyst_v1.md`](src/proofbench/agents/prompts/contract_analyst_v1.md) | `read_file`, `search_tree`, `inspect_schema`, `inspect_roles` | Execute SQL, write anything, read the oracle |
| **Adversarial Test Designer** | Choose worlds from a fixed catalog and name the invariant each threatens | [`test_designer_v1.md`](src/proofbench/agents/prompts/test_designer_v1.md) | `list_worlds`, `inspect_schema`, `inspect_roles` | Read arbitrary files, invent a world, express a command |
| **Remediation Engineer** | Propose the smallest correction after a candidate is blocked | [`remediation_engineer_v1.md`](src/proofbench/agents/prompts/remediation_engineer_v1.md) | `read_file`, `read_evidence`, `inspect_schema` | Search the tree, touch a policy, oracle or trace, weaken a check |

A fourth agent exists only for the baseline arm:

| Agent | Job | Instructions |
| --- | --- | --- |
| **Direct reviewer** | The PRD-FR-002 baseline: approve, reject, or ask for clarification, given the same material as the final workflow | [`direct_reviewer_v1.md`](src/proofbench/agents/prompts/direct_reviewer_v1.md) |

## Mediated tools

No agent reaches a file, a database, or a process directly. Every action becomes
a typed `ToolRequest` and passes through `tools/router.py`, which decides before
anything executes whether *this* actor may call *this* tool.

- Capabilities are per actor, not global. Splitting one agent into three buys
  nothing if they share one capability set.
- A refusal is returned as a recorded refusal, never as an empty result. An agent
  that cannot tell "denied" from "found nothing" will build a contract on an
  absence it never knew about.
- Output is capped and redacted before it reaches the agent.
- Path resolution goes through the same containment the case loader uses, so an
  agent gets exactly the boundary the product does — including the refusal to
  resolve anything under `evaluator_only/`.

## Providers

| Mode | Adapter | Used by | Network |
| --- | --- | --- | --- |
| `fake` | `providers/fake.py` | Every command on the judge path | None |
| `live` | `providers/live.py` | `make evaluate-live` only | Anthropic Messages API |
| `none` | — | Deterministic runs with `--no-agents` | None |

The fake provider serves **recorded** responses from
`benchmark/aidledger/cases/<id>/agent_fixtures/`. Recorded rather than generated:
the offline judge path has to produce identical agent artifacts on every machine,
and a provider that improvised would break replay before it broke anything else.
It reports zero token usage rather than inventing a number that would end up in a
cost table someone reads as measurement.

The live adapter targets `claude-opus-5` with adaptive thinking. It is
implemented and **has not been run** — see `results/comparison.md`. The Anthropic
SDK is an optional extra that `make bootstrap` does not install.

## Retries and failure

One schema repair attempt, carrying the validation errors back. A second invalid
response ends the stage as `EVIDENCE_INCOMPLETE` with **both** responses
preserved. Retrying until something parses would select for parseability rather
than correctness, and would quietly turn a confused agent into a confident one.

## Human checkpoints

There is exactly one, and it is not an approval step.

When the Contract Analyst raises an authority question — a business fact that no
amount of code or data can settle — the workflow stops and returns
`DOMAIN_RULING_REQUIRED` with a ruling packet: the exact question, the affected
rows counted per tenant, the competing readings, what each costs if wrong, what
was already checked, and the qualification the answer requires.

A ruling must be scoped and executable. `Ruling` has no field for "looks fine";
scope, determination column, determination value and justification are all
required, so a signature has nowhere to go. The ruling compiles into a constraint
the money world checks.

**A ruling cannot override a deterministic failure.** Decision precedence puts a
confirmed blocking finding above any authority question. A domain owner settles
what the data cannot say; they do not overrule what the database demonstrated.

Worked example: C04 with `currency-uniformly-usd.yaml` reaches
`READY_FOR_REVIEW`; the same candidate with `currency-per-organisation.yaml`
reaches `BLOCKED`. The gate is a question, not a veto.

## Trajectories

Every run writes an append-only `trajectory.jsonl` with a SHA-256 chain, and a
readable `trajectory.md` compiled from it. Traces record observable actions only:
messages sent, structured responses, tool requests and results, retries, state
transitions, timings and artifact references. **No hidden chain-of-thought is
recorded**, and none is reconstructed.

Redaction runs *before* hashing. Hashing a secret and removing it afterwards
would commit the chain to its value.

Representative trajectories are indexed in
[`submission/trace-index.md`](submission/trace-index.md).
