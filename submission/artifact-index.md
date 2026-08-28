# Artifact index

Every claim this submission makes, and the file that supports it. A row with no
artifact is a claim this project does not make.

## Headline claims

| Claim | Artifact | How to check it yourself |
| --- | --- | --- |
| The visible-tests baseline lets 9 of 9 unsafe migrations through | `results/summary.json` → `primary_metric.by_arm.baseline_visible_tests` | `make evaluate` |
| ProofBench lets 0 of 9 through | `results/summary.json` → `primary_metric.by_arm.migration_court` | `make evaluate` |
| Both arms accept both safe controls | `results/comparison.md`, guardrail table | `make evaluate` |
| The summary follows from the raw runs | `results/raw-runs.jsonl` | `make evaluate` recomputes and fails on disagreement |
| Every unsafe candidate passes its own visible test | `tests/golden/*/certificate.json` → `visible_tests` | `uv run pytest tests/e2e/test_all_cases.py -k visible` |
| All 12 certificates reproduce offline | `tests/golden/*/` | `make replay` |
| The five-command path works from a clean checkout with no key | `REPRODUCTION.md`, measured timings | `git clone` then the five commands |

## Product behaviour

| Claim | Artifact |
| --- | --- |
| Three agents with separate jobs, none able to decide | `submission/trace-index.md`; `tests/unit/test_agent_boundaries.py` |
| Deterministic checks make the decision | `tests/golden/*/decision.json`; `src/proofbench/decision/policy.py` |
| C01's tenant leak is confirmed, not asserted | `tests/golden/C01/certificate.md` — role, tenant, operation and row keys, each citing the check that observed it |
| A human is asked only for domain authority | `tests/golden/C04/ruling-packet.md` |
| A ruling is executable, and cannot override a failed check | `benchmark/aidledger/cases/C04/rulings/`; `tests/e2e/test_c04_authority.py` |
| The correction passes on rerun, and the decision stays BLOCKED | `tests/golden/C01/certificate.json` → `correction.verified` alongside `decision.external_state` |
| Untrusted SQL cannot escalate | `tests/security/test_migration_containment.py` |
| The oracle is never readable by product code | `tests/security/test_oracle_boundary.py` |

## Evidence for the changelog

| Claim | Artifact |
| --- | --- |
| Each iteration is linked to evidence | `results/improvement-changelog.md` |
| An experiment was removed, with the evidence that removed it | Same file, "Removed, and why" — three of them |
| The highest-impact change is named | Same file, "The change that contributed most" |

## Claims deliberately **not** made

| Not claimed | Why |
| --- | --- |
| ProofBench beats a direct-review *agent* | That baseline is implemented but unrun; it needs a provider key. `results/comparison.md` states this in the report itself |
| Human time saved per task | Not measured. A number nobody timed would be worse than an absence |
| "Migration correctness is a property of the deployment timeline" as a finding | Stated as a hypothesis in `README.md`. It becomes a finding only under PRD §16, which needs a recorded unsafe case that passes its visible check and fails a timeline world — nine of them exist, so this row is a candidate for unlocking |
| Any measured cost figure | Every judge-path command costs zero; the live arm has not run |

## Where the numbers live

`results/summary.json` is the only file a metric may be quoted from. It carries
numerator and denominator for every rate. `make evaluate` proves it follows from
`results/raw-runs.jsonl`, so a number in a slide cannot drift from the runs it
came from.
