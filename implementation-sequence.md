# ProofBench Migration Court implementation sequence

## 1. Delivery objective

Ship one complete, reproducible proof before adding breadth:

> A fair direct-review agent assesses C01, Migration Court runs the same candidate through a tenant-isolation world, deterministic evidence blocks the unsafe migration, a bounded correction reruns, and the final Migration Change Certificate replays offline.

That vertical must work by the end of Day 1. Day 2 expands it to all 12 fixed cases and the human authority path. Day 3 is reserved for the frozen experiment, reproduction, documentation, and video.

## 2. Build rules

1. Build deterministic code before live agents.
2. Keep the oracle physically separate from the product workflow.
3. Finish the certificate data model before styling it.
4. Add one world only with a known-failing and known-passing test migration.
5. Keep baseline and final inputs identical.
6. Treat timeouts, trace failures, and replay differences as product states.
7. Do not start deferred work while a release gate is red.
8. Commit evidence after every experiment, including failures.

## 3. Critical path

```text
schemas
  -> frozen C01 fixture
  -> PostgreSQL sandbox
  -> RLS world
  -> decision policy
  -> certificate model
  -> offline replay
  -> trace writer
  -> fake-provider agent workflow
  -> C04 authority path
  -> remaining worlds and 12 cases
  -> fair baseline
  -> frozen paired evaluation
  -> documentation and video
```

No UI framework, API, broad mutation engine, or extra provider belongs on this path.

## 4. Phase 0: kickoff compliance and scope freeze

Time box: 60 minutes after the final challenge materials are released.

### Work

- Read the final problem, acceptance tests, runtime limits, and submission terms.
- Record any conflict with this plan in `docs/kickoff-delta.md`.
- Label pre-existing work and hackathon work in the README and changelog.
- Freeze the P0/deferred cut from PRD section 6.
- Confirm PostgreSQL, Docker, Python 3.12, external provider, and network policies are permitted.
- Freeze five judge commands and expected output directories.
- Create `results/experiment-draft.json` without results.

### Evidence

- `docs/kickoff-delta.md`
- commit timestamp and clean status record
- dependency and license inventory
- initial Improvement Changelog entry

### Exit gate S0, maps to R0

- No final-brief constraint is unresolved.
- The submission can still use a local PostgreSQL sandbox.
- P0 fits a three-day solo build.

If PostgreSQL containers are forbidden, preserve the product shape but swap the runner for the prescribed environment. Record this as a scope change, not a hidden deviation.

## 5. Phase 1: repository, schemas, and fake provider

Target: Day 1, hours 1 to 3.

### Work order

1. Create the repository layout from the technical plan.
2. Add `pyproject.toml`, `uv.lock`, Makefile, Dockerfile, and Compose file.
3. Define Pydantic models for case, contract, world plan, result, decision, ruling, trace, metrics, manifest, and certificate.
4. Add JSON Schema export and golden schema snapshots.
5. Implement typed domain errors and exit codes.
6. Implement `FakeProvider` with fixture responses for all three agents.
7. Add CLI shells for `case validate`, `review`, `evaluate`, `trace validate`, `certificate verify`, and `replay`.

### Tests

- every schema accepts one minimal valid fixture;
- missing and unknown fields fail with useful locations;
- all four product states serialize exactly;
- fake-provider outputs validate without repair;
- CLI help and invalid-command exit codes are tested.

### Exit gate S1

- `make bootstrap` succeeds from a clean virtual environment.
- `make test` can run schema and CLI tests.
- C01 case metadata validates.

PRD coverage: PRD-FR-001, PRD-NFR-001, PRD-NFR-006.

## 6. Phase 2: C01 deterministic vertical

Target: Day 1, hours 3 to 7.

### Work order

1. Build the AidLedger base schema, roles, row-level-security policies, and synthetic fixtures.
2. Write C01 candidate SQL that recreates `payments` without restoring row-level security.
3. Add visible tests that check the final columns and basic reads but do not reveal the oracle.
4. Add evaluator-only expected label and blast-radius assertions.
5. Implement disposable Compose project lifecycle.
6. Implement initial state hashing and fixture verification.
7. Implement the RLS role-by-tenant matrix.
8. Implement deterministic decision precedence.
9. Compute confirmed affected roles, tenants, and accessible rows.

### Tests

- safe base schema enforces every role rule;
- C01 passes its visible final-schema test;
- C01 fails the RLS world;
- a corrected C01 passes the same world;
- a world timeout becomes `EVIDENCE_INCOMPLETE`;
- evaluator-only files cannot be resolved inside the product container.

### Exit gate S2

- One command produces `BLOCKED` for C01 with a decisive check and confirmed blast radius.
- The decision is produced without a model call.
- Container cleanup succeeds after pass, fail, and timeout.

PRD coverage: PRD-FR-030, 031, 040, 041; PRD-NFR-002 and 003.

## 7. Phase 3: certificate, trace, and replay vertical

Target: Day 1, hours 7 to 10.

### Work order

1. Implement append-only JSONL writer and event hash chain.
2. Trace intake, state changes, checks, decision, artifacts, and errors.
3. Build the canonical certificate model.
4. Render plain Markdown and static HTML with the seven first-screen fields.
5. Build `manifest.json` with input, output, prompt, policy, environment, and image hashes.
6. Implement offline replay and semantic comparison.
7. Commit a sanitized C01 golden bundle.

### Tests

- changing an event breaks trace validation;
- redaction removes test secrets and host-only paths;
- JSON, Markdown, and HTML share the same state and decisive invariant;
- replay passes from a fresh database;
- replay exits nonzero when candidate, policy, trace, or result changes;
- provider variables are unset during replay test.

### Exit gate S3, maps to R1

- C01 produces a readable certificate and valid trace.
- `make replay` reproduces C01 without a model call.
- A reviewer can see the decision, blast radius, next action, and replay command in the first HTML viewport.

PRD coverage: PRD-FR-050, 052, 053, 060, 061.

### Day 1 stop condition

Do not leave Day 1 with several partial worlds. Leave it with one full proof.

## 8. Phase 4: mediated agents and bounded correction

Target: Day 2, hours 1 to 4.

### Work order

1. Implement provider interface, retry budget, usage accounting, and schema repair.
2. Implement typed tool router and actor/state allowlists.
3. Write versioned instructions for the Contract Analyst.
4. Write versioned instructions for the Adversarial Test Designer.
5. Write versioned instructions for the Remediation Engineer.
6. Run all three first with `FakeProvider`.
7. Add one live-provider path if final rules allow it.
8. Connect C01: contract, world selection, failure, correction, clean rerun.
9. Compile the assumption-to-failure-to-correction narrative.

### Tests

- Contract Analyst cannot edit files or execute SQL;
- Test Designer cannot create arbitrary commands or edit the candidate;
- Remediation Engineer cannot change policies, traces, or evaluator files;
- invalid agent output gets one repair attempt;
- a second invalid output returns `EVIDENCE_INCOMPLETE`;
- original and corrected candidate hashes both remain in the bundle;
- only deterministic results change the external state.

### Exit gate S4

- C01 completes with three representative agent trajectories.
- The correction is bounded and the rerun starts from a clean fixture.
- The trace compiler shows assumption, failed check, feedback, correction, and verified result.

PRD coverage: PRD-FR-010 to 012, 042, 050, 051.

## 9. Phase 5: human authority path with C04

Target: Day 2, hours 4 to 6.

### Work order

1. Build C04 with historical rows lacking currency evidence.
2. Implement the authority classifier using contract fields and policy, not a general “ask human” branch.
3. Render a ruling packet with the exact question, affected rows, competing interpretations, consequences, checked evidence, and reviewer qualification.
4. Define a versioned ruling file format.
5. Compile an accepted ruling into an executable currency invariant.
6. Rerun only the affected worlds from a clean sandbox.
7. Prove that a human ruling cannot suppress a separate deterministic failure.

### Tests

- C04 reaches `DOMAIN_RULING_REQUIRED` before a ruling;
- a free-form approval is rejected;
- an out-of-scope ruling is rejected;
- a valid ruling changes input and certificate hashes;
- currency checks use integer minor units;
- a ruling plus an RLS failure still returns `BLOCKED`.

### Exit gate S5

- C04 demonstrates a genuine human authority boundary.
- The certificate names the ruling, scope, reviewer role, and affected invariant.

PRD coverage: PRD-FR-020, 021, 032.

## 10. Phase 6: remaining worlds and cases

Target: Day 2, hours 6 to 12.

Implement in this order because each step reuses prior infrastructure:

1. C03 and the money/reconciliation world.
2. C05 and the rolling compatibility world.
3. C06 and the interruption/resume controller.
4. C08 and concurrent-write rollback.
5. C09 as retry idempotency in the money and rolling worlds.
6. C07 and the lock-budget probe.
7. C10 and the audit-history check.
8. C02 as a wider RLS role matrix.
9. C11 as the simple known-good control.
10. C12 as the difficult known-good control.

For each case:

- write candidate and visible tests;
- write evaluator oracle and expected blast radius;
- prove visible tests do not reveal the answer;
- add one known-failing and one known-passing world test;
- generate fake-provider agent artifacts;
- generate and replay the golden certificate;
- add the case hash to the frozen manifest.

### Exit gate S6, maps to R2 and R3

- All 12 cases reach their expected offline state.
- C11 and C12 reach `READY_FOR_REVIEW`.
- C04 requires authority.
- All nine unsafe candidates are blocked by at least one executed check.
- Every case has a replayable golden certificate.

PRD coverage: PRD-FR-030 to 037 and Gate R3.

### Day 2 stop condition

Freeze features at this point. If any case is unstable, simplify its mechanics while preserving the registered risk. Do not add a web application.

## 11. Phase 7: fair baseline and experiment stages

Target: Day 3, hours 1 to 3.

### Work order

1. Freeze the direct-review baseline prompt and common budget.
2. Confirm baseline and final arms receive the same candidate, repository, visible tests, policy, model family, and total agent budget.
3. Run B0 on all cases before reading aggregate results.
4. Run E1 equal-budget self-review.
5. Confirm E2 through E5 changelog artifacts from retained components.
6. Time-box E6 targeted mutation or agent debate to 45 minutes.
7. Retain E6 only if it improves an observed guardrail or primary outcome without breaking replay or schedule.
8. Record the removed experiment and why it was removed.

### Exit gate S7

- The baseline is credible and reproducible.
- At least one removed experiment has linked evidence.
- No experiment result changes the frozen case manifest.

PRD coverage: PRD-FR-002 and 073.

## 12. Phase 8: frozen paired evaluation

Target: Day 3, hours 3 to 6.

### Work order

1. Write `results/experiment.json` before the first final run.
2. Record commit, dirty status, provider, model, prompts, budgets, seeds, image digest, host resources, and protocol.
3. Run the preferred 72-run protocol if time and cost fit.
4. Otherwise run all 12 cases once in both arms and repeat C01, C04, C08, and C12 three times.
5. Keep every completed, timed-out, invalid, and failed run.
6. Reveal evaluator oracles only after each decision closes.
7. Compute count-first primary and guardrail metrics.
8. Generate per-case CSV, summary JSON, and comparison report.

### Required checks

- unsafe denominator is nine per complete repeat;
- C11 and C12 are reported separately as safe controls;
- C04 is not counted as an unsafe block unless its oracle defines an unsafe candidate after a ruling;
- `EVIDENCE_INCOMPLETE` is reported, not counted as safe;
- percentages always include numerator and denominator;
- experiment hash covers inputs, code, prompts, and protocol.

### Exit gate S8, maps to R4

- `results/summary.json` accounts for every scheduled run.
- Primary metric and guardrails recompute from `raw-runs.jsonl`.
- Comparison report does not contain unsupported causal claims.

PRD coverage: PRD-FR-070 to 073.

## 13. Phase 9: reproduction and submission hardening

Target: Day 3, hours 6 to 9.

### Work order

1. Clone or copy the repository into a new temporary directory.
2. Remove provider environment variables.
3. Run the five judge commands exactly as documented.
4. Record wall time, downloads, expected output, and any platform caveats.
5. Verify certificate manifests and trace chains.
6. Validate that evaluator files and credentials are absent from submitted traces.
7. Run Ruff, mypy, full pytest, security tests, and golden replay.
8. Generate a submission inventory and archive checksum.

### Required documents

- `README.md`: user, bottleneck, value, quick start, main failure mode, hot take;
- `REPRODUCTION.md`: clean setup, exact commands, expected output, versions, runtime, cost;
- `CHANGELOG.md` or `results/improvement-changelog.md`: each material iteration and evidence;
- `AGENT_DISCLOSURE.md`: every agent, provider, instruction, tool, checkpoint, and trajectory;
- `submission/trace-index.md`: representative trajectory per agent;
- `submission/artifact-index.md`: claim-to-file map.

### Exit gate S9, maps to R5

- All five judge commands pass in the clean directory.
- Offline replay makes no provider request.
- `make baseline` and `make evaluate` validate or recompute committed evidence without regenerating model calls.
- The documented runtime and outputs match the recorded run.

## 14. Phase 10: certificate polish and five-minute video

Target: Day 3, hours 9 to 12.

### Work order

1. Apply final visual hierarchy to static HTML without changing certificate data.
2. Confirm the first viewport shows the seven PRD-FR-060 fields.
3. Rehearse the presentation from `5-min-presentation.md`.
4. Replace every metric sentence with the exact on-screen result from `results/summary.json`.
5. Remove any line whose claim-lock evidence is missing.
6. Record the deterministic replay, not a fragile live provider run.
7. Keep a static certificate and recorded terminal output ready for editing fallback.
8. Check the final video is at most five minutes.

### Exit gate S10, maps to R6

- The video names all six rubric categories in natural language.
- The video includes problem, baseline, one realistic run, final comparison, changelog, highest-impact change, one removed experiment, and hot take.
- Every spoken feature and number links to an artifact in the presentation claim-lock table.

## 15. Test execution order

Run the smallest useful gate after each edit:

```bash
uv run pytest tests/unit/path_to_changed_test.py
uv run ruff check src tests
uv run mypy src
uv run pytest tests/integration/path_to_changed_world.py
```

Before each phase exit:

```bash
make test
```

Before submission:

```bash
make bootstrap
make test
make baseline
make evaluate
make replay
```

## 16. Failure recovery rules

| Failure                         | Response                                                                                    |
| ------------------------------- | ------------------------------------------------------------------------------------------- |
| Docker startup is slow          | Pre-pull in bootstrap; keep runtime measured; do not hide startup cost                      |
| Lock timing is noisy            | Use conservative thresholds and repeat the world; report environment                        |
| Live provider is unavailable    | Use recorded live trajectories for submission evidence and fake provider for offline replay |
| Agent output fails schema twice | End as `EVIDENCE_INCOMPLETE`; preserve both responses                                       |
| One case cannot stabilize       | Simplify its fixture, keep its registered invariant, rerun both arms                        |
| Evaluation budget is low        | Use the documented fallback protocol, never drop the 12-case paired pass                    |
| Certificate styling breaks      | Fall back to plain static template generated from canonical JSON                            |
| Replay differs                  | Stop claims, find the volatile or uncontrolled input, rerun the experiment after fixing it  |
| Video demo fails                | Use the pre-recorded replay and verified static certificate                                 |

## 17. Scope cuts in order

Cut these first:

1. E6 mutation or debate experiment.
2. Live agent correction in the recorded demo; show the verified recorded correction instead.
3. Extra HTML charts and animation.
4. More than the fallback evaluation repeats.
5. Any integration outside the local CLI.

Never cut:

- all 12 fixed cases;
- two known-good controls;
- fair baseline;
- oracle separation;
- deterministic decision policy;
- trajectory capture;
- offline replay;
- primary metric with counts;
- five required submission deliverables.

## 18. Final completion checklist

- [x] R0: scope, provenance, and case integrity are frozen.
- [x] R1: C01 deterministic vertical, certificate, and replay pass.
- [x] R2: three agent roles and C04 human authority path pass.
- [x] R3: all 12 golden cases reach expected states.
- [ ] R4: paired comparison and changelog are complete.
- [ ] R5: clean five-command reproduction passes without a model key.
- [ ] R6: code, guide, video, trajectories, and claims agree.
- [ ] No required test, trace, result, or artifact is pending.

The sequence ends only when every checked item has fresh evidence from the submission commit.
