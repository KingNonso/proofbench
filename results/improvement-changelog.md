# Improvement Changelog

How this solution evolved, with each entry linked to the evidence that decided
it. Required by hackathon deliverable 01 and PRD-FR-073.

Every metric below comes from `results/summary.json`, which recomputes from
`results/raw-runs.jsonl` — `make evaluate` proves it. Rows marked *not run* have
no number and make no claim.

## Experiment stages

| Stage | What was tried and why | Evidence | Decision |
| --- | --- | --- | --- |
| **B0** | Visible-tests baseline: run the checks already in CI and merge if they pass — the process this product means to improve on | `results/summary.json`, arm `baseline_visible_tests`: unsafe escape **9/9** | Kept as the measured baseline |
| **B0-agent** | Direct-review agent baseline (PRD-FR-002): one general-purpose reviewer, same candidate, schema, roles, policy, tests, model family and budget | *Not run* — needs a provider key | Implemented (`evaluation/baseline.py`, `agents/prompts/direct_reviewer_v1.md`); `make evaluate-live` runs it. No claim is made about it until it does |
| **E1** | Equal-budget self-review | *Not run* — depends on B0-agent | Deferred, not abandoned |
| **E2** | Typed Migration Contract: agents emit facts, assumptions and authority questions, with no field for a verdict | C04 reaches `DOMAIN_RULING_REQUIRED`; with `--no-agents` the same case reaches `READY_FOR_REVIEW` | **Kept.** It is the only thing that detects C04 |
| **E3** | Tenant and row-level-security world | C01 and C02 blocked on `INV-RLS-001` / `INV-RLS-002` with confirmed blast radius | **Kept** |
| **E4** | Money, rolling, interruption, rollback, lock and audit worlds | C03, C05–C10 each blocked by the world that covers them; C12 passes all seven | **Kept.** Each world is the only thing that catches its case |
| **E5** | Authority-aware human gate | C04: no ruling → asks; ruling of USD → `READY_FOR_REVIEW`; ruling of per-organisation currency → `BLOCKED` on `INV-MONEY-002` | **Kept.** Both determinations were exercised, so the gate is a question rather than a veto |
| **E6** | Targeted mutation or agent debate | *Not attempted* | Cut. `implementation-sequence.md` §17 lists it first to cut, and the budget went to the twelve cases instead |
| **Final** | Twelve cases, seven worlds, three agents, deterministic decision | Unsafe escape **0/9**, safe accepted **2/2**, authority asked **1/1**, replay **12/12** | Shipped |

## Removed, and why

These were built, measured, and taken out. Each was removed because evidence said
so, not because of taste.

### The lock world's contention design

**Tried.** A second session held a conflicting lock while the candidate statement
ran under `lock_timeout`, and SQLSTATE 55P03 was the finding.

**Evidence.** It failed C12 — the *correct* migration. Every `ALTER TABLE` takes
ACCESS EXCLUSIVE and therefore blocks behind any open reader, so the design
condemned the safe candidate alongside the reckless one. A check that fires on
both is not a check.

**Replaced with.** A comparison of `pg_relation_filenode` across the statement. A
table rewrite changes the filenode; a metadata-only change does not. That is the
fact that actually distinguishes C07 from C12, and it is identical on every
machine and independent of fixture size — which a stopwatch could never be.

### Folding a passing correction into the decision

**Tried.** After the Remediation Engineer's correction passed a clean rerun, the
run reported `READY_FOR_REVIEW`.

**Evidence.** C01 — an unsafe candidate — came out as `READY_FOR_REVIEW`. Under
PRD-FR-071 that is an escape, and with remediation enabled every unsafe case
would have escaped, making the primary metric measure nothing.

**Replaced with.** The decision is about the candidate as submitted. The
correction is its own certificate section, marked as not changing the decision.

### A `Ruling` validator that could never fire

**Tried.** A word-list rejecting `ruling_text` of "approved", "lgtm" and similar.

**Evidence.** `min_length=20` on the same field rejected every one of those first,
so the validator was unreachable. mypy and a test both showed it dead.

**Replaced with.** Nothing — the structural requirement already did the work.
Scope, determination column, determination value and justification are all
required, so a signature has nowhere to go. Dead validation is worse than none,
because it looks like protection.

## The change that contributed most

The **worlds**, and specifically the fact that there are seven of them. The
baseline's 9/9 escape rate is not a story about one clever check: every one of
the nine unsafe candidates passes its own visible test, and each is caught by a
different world. Removing any single world would move the final escape rate from
0/9 to 1/9.

That is also the honest limit of the result. The measured comparison is against
the *visible-tests* baseline. Whether a reviewing agent given the same material
would do better is the open question, and it needs `make evaluate-live` and a key
before anyone says otherwise.

## Human time per task

The brief's metric table asks for human time per task. It is **not measured
here**, and a number nobody timed would be worse than an absence. What can be
said from the artifacts: the baseline arm gives a reviewer a pass/fail with no
evidence attached, while the final arm produces a certificate whose first screen
carries the decisive invariant, the confirmed blast radius with row keys, and the
next action. Measuring what that is worth needs reviewers and a stopwatch.
