# ProofBench Migration Court product requirements document

## Document control

| Field              | Value                                                         |
| ------------------ | ------------------------------------------------------------- |
| Product            | ProofBench Migration Court                                    |
| Tagline            | The pre-merge trial for AI-written database migrations        |
| Release            | Hackathon submission MVP                                      |
| Primary user       | Staff database or platform engineer                           |
| Flagship benchmark | AidLedger, a fictional multi-tenant cash-assistance system    |
| Primary metric     | Unsafe migration escape rate                                  |
| Canonical status   | Revised for the official Frontier Engineering Challenge brief |

This document is the product contract. The technical plan explains how to satisfy it. The implementation sequence fixes the build order. The presentation may claim only features and results allowed by this PRD's claim rules.

## 1. Product summary

ProofBench Migration Court reviews a candidate PostgreSQL migration already produced by a coding agent. It answers one question:

> Is this migration ready for a qualified engineer to review, or is there evidence that it must be blocked or clarified first?

The product does not ask an agent to grade its own work. Three agents reconstruct the intended contract, design adversarial migration worlds, and propose a minimal correction after a failure. Deterministic PostgreSQL checks make the safety decision.

The final output is a Migration Change Certificate in JSON, Markdown, and static HTML. It records the decision, failed or passed invariants, confirmed blast radius, human rulings, correction, verification evidence, trace, and replay command.

The hackathon proof uses 12 fixed AidLedger migrations. The same candidate files, repository state, visible tests, model, and limits are used for the direct-review baseline and Migration Court. The headline result is the difference in unsafe migration escape rate.

## 2. Why this problem matters

### 2.1 User bottleneck

Coding agents can produce SQL that looks reasonable and passes visible tests. A reviewer still has to answer questions that a final-schema diff does not settle:

- Does row-level security still protect every database role?
- Can the old and new application versions run during a rolling deployment?
- Can an interrupted backfill resume without duplicating money?
- Does rollback preserve writes made after the migration began?
- Does the migration exceed the team's lock-time policy?
- Is a historical data assumption supported, or does a domain owner need to rule on it?

The reviewer must collect this evidence by hand or approve with incomplete evidence. Both paths are expensive. The second can be dangerous.

### 2.2 Consequences

The benchmark models four concrete risks:

- cross-tenant data disclosure;
- duplicate or incorrect disbursements;
- lost or mutable audit history;
- failed deploys and destructive rollback.

ProofBench uses synthetic data and a sandbox. It does not act on a live database.

### 2.3 Product thesis

The working thesis is:

> Migration correctness is a property of the deployment timeline, not the final schema.

This is a hypothesis before evaluation. It becomes a submission finding only if recorded cases show timeline checks catching unsafe migrations that the baseline accepted.

## 3. Users and jobs

### 3.1 Primary user: database or platform engineer

They review AI-written changes before merge.

Their job is: “Give me a compact, replayable account of what this migration can do to tenant boundaries, money, compatibility, availability, and rollback so I can focus my judgment on the unresolved part.”

Their success condition is a clear decision with evidence and a next action, not a long chat transcript.

### 3.2 Required human: qualified domain reviewer

This person owns a business fact that code cannot determine. In AidLedger, an example is whether historical payments without a currency field are legally known to be USD.

Their job is: “Show me the exact ambiguity, its impact, the competing interpretations, and the smallest ruling needed.”

Their response becomes a versioned executable invariant. It does not erase a confirmed integrity or tenant-isolation failure.

### 3.3 Evaluation user: hackathon judge

The judge needs to run the project from a clean environment, inspect one end-to-end case, compare the baseline with the final system, and trace every result to an artifact.

### 3.4 Benchmark beneficiary, not buyer

AidLedger is a fictional humanitarian cash-assistance system. It gives the benchmark a high-stakes, understandable domain. AidLedger is not the primary customer and does not broaden the product into charity operations software.

## 4. Positioning and boundaries

ProofBench sits between AI code review, database change management, and agent evaluation.

Its narrow claim is that replayable migration worlds provide stronger review evidence than a direct agent opinion on the same candidate migration. It does not claim formal verification, guaranteed safety, support for every PostgreSQL feature, or production readiness.

The product reviews an existing candidate migration. It does not use one open-ended agent loop to write, judge, and approve the same change. A remediation agent may propose a correction only after the candidate is blocked or a human ruling is recorded.

## 5. Product principles

1. Evidence outranks confidence. Agent prose cannot turn a failed deterministic check into a pass.
2. The deployment timeline is the unit of verification. Final schemas alone are insufficient.
3. Human attention is reserved for authority, not routine confirmation.
4. Every headline claim must resolve to a recorded artifact.
5. A baseline must be plausible and fairly funded.
6. The judge path must work without a model key.
7. The narrow vertical must finish before optional platform work begins.
8. Traces record observable actions, not hidden chain-of-thought.

## 6. Goals, non-goals, and release cut

### 6.1 P0 goals

- Review one supplied PostgreSQL migration through a typed CLI workflow.
- Run three purposeful agents behind mediated tools.
- Execute fixed PostgreSQL 16 migration worlds in Docker.
- Enforce row-level security, financial, compatibility, interruption, rollback, lock, and audit invariants.
- Return one of four explicit product states.
- Produce a replayable Migration Change Certificate.
- Compare a direct-review baseline with Migration Court on 12 pre-registered cases.
- Export readable agent-use trajectories for every agent.
- Reproduce the golden run offline in five commands.

### 6.2 Deferred work

- FastAPI service and hosted control plane;
- React or Next.js application;
- GitHub App or automatic pull-request comments;
- OpenTelemetry and Jaeger;
- Ed25519 signatures;
- distributed workers;
- database engines other than PostgreSQL;
- general code review outside migrations;
- broad mutation testing;
- automatic merge or production execution.

### 6.3 Stop rule

Optional work starts only after all P0 release gates in section 17 pass. If time is short, cut visual motion and extra benchmark analysis before cutting replay, traces, fair evaluation, or the certificate.

## 7. Product decisions and states

ProofBench returns exactly one external state:

| State                    | Meaning                                                                                                                        | Required next action                                 |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------- |
| `READY_FOR_REVIEW`       | All required evidence checks passed. This is not an automatic approval.                                                        | Qualified engineer reviews the certificate and code. |
| `BLOCKED`                | At least one blocking safety invariant failed.                                                                                 | Correct the candidate and rerun.                     |
| `DOMAIN_RULING_REQUIRED` | A material business fact cannot be derived from allowed evidence.                                                              | Qualified domain owner records a scoped ruling.      |
| `EVIDENCE_INCOMPLETE`    | The system could not produce trustworthy evidence because a run timed out, replay diverged, a trace failed, or a budget ended. | Fix the evidence failure and rerun.                  |

Confirmed row-level security, integrity, money, rollback, or audit failures cannot be overridden into `READY_FOR_REVIEW` by a human response.

## 8. Benchmark contract

### 8.1 AidLedger fixture

AidLedger stores organizations, beneficiaries, payment instructions, disbursements, currencies, and immutable audit events. PostgreSQL row-level security separates tenants. Application roles include a tenant worker, organization administrator, auditor, and service process.

All names, identities, amounts, and events are synthetic. The fixture contains no private or production data.

### 8.2 Pre-registered cases

The manifest is frozen before the final experiment. Each case contains the candidate migration, starting schema, visible tests, evaluator-only oracle, expected decision class, expected blast radius, and replay seed.

| ID  | Candidate defect or property                                                                                           | Expected state           |
| --- | ---------------------------------------------------------------------------------------------------------------------- | ------------------------ |
| C01 | Recreates `payments` without row-level security                                                                        | `BLOCKED`                |
| C02 | Restores tenant policy for the app role but omits auditor and organization-admin rules                                 | `BLOCKED`                |
| C03 | Converts minor currency units through floating point                                                                   | `BLOCKED`                |
| C04 | Assumes every historical payment is USD without allowed evidence                                                       | `DOMAIN_RULING_REQUIRED` |
| C05 | Drops the old column while the old application still writes it                                                         | `BLOCKED`                |
| C06 | Uses a non-idempotent backfill that duplicates effects after interruption                                              | `BLOCKED`                |
| C07 | Takes an exclusive lock longer than the declared policy budget                                                         | `BLOCKED`                |
| C08 | Rollback loses records written after the migration begins                                                              | `BLOCKED`                |
| C09 | A retried dual-write path duplicates a disbursement                                                                    | `BLOCKED`                |
| C10 | Removes or mutates required audit history                                                                              | `BLOCKED`                |
| C11 | Valid expand, backfill, verify, and contract migration                                                                 | `READY_FOR_REVIEW`       |
| C12 | Valid difficult migration survives rolling versions, interruption, concurrent writes, row-level security, and rollback | `READY_FOR_REVIEW`       |

The unsafe set is C01, C02, C03, and C05 through C10. C04 tests authority escalation. C11 and C12 prevent a reject-everything system from appearing successful.

### 8.3 Oracle separation

Agents may read the task, candidate migration, repository, visible tests, policy file, and tool results exposed by the workflow. They may not read expected labels, evaluator-only fixtures, unsafe-case annotations, or oracle assertions.

The evaluator process mounts the oracle only after the product decision is final. Oracle access is logged. A run with earlier oracle access is invalid and remains in the result set as an integrity failure.

## 9. End-to-end user journey

1. The engineer runs `proofbench review cases/C01/case.yaml`.
2. The intake layer hashes the repository, candidate, policy, prompts, model configuration, and environment.
3. The Contract Analyst separates facts, assumptions, invariants, and authority questions.
4. If a business fact requires authority, the workflow returns `DOMAIN_RULING_REQUIRED` with a ruling packet.
5. The Adversarial Test Designer selects fixed migration worlds and adds bounded case-specific attacks.
6. The deterministic runner creates a fresh PostgreSQL sandbox and executes those worlds.
7. The decision engine maps evidence to a product state.
8. For a blocked candidate, the Remediation Engineer may produce a minimal expand, backfill, verify, and contract correction.
9. The corrected candidate reruns from a clean sandbox. Previous failures remain in the trace.
10. The certificate compiler writes JSON, Markdown, and static HTML.
11. A reviewer or judge runs the replay command and verifies hashes and decisions without a model call.

## 10. Functional requirements

Each requirement has an identifier used by the implementation and presentation documents.

### 10.1 Intake and fair inputs

#### PRD-FR-001: Validate and freeze the case

The system must validate the case schema, resolve only allowed paths, and create content hashes for every input. The frozen record must include tool versions, prompt versions, model identifier, seed, time and token budgets, and container image digest.

Acceptance:

- invalid or missing fields return a typed error;
- changing a candidate or policy changes the run hash;
- evaluator-only files are excluded from agent mounts.

#### PRD-FR-002: Run a fair direct-review baseline

The baseline must give one general-purpose coding agent the same candidate, repository, visible tests, model family, and budget available to the final workflow. It returns `approve`, `reject`, or `clarify`, plus its observable trace.

Acceptance:

- baseline prompts and budgets are versioned;
- no deliberately misleading prompt weakens the baseline;
- the evaluator maps baseline decisions to the common metric schema.

### 10.2 Agent responsibilities

#### PRD-FR-010: Contract Analyst

The Contract Analyst must emit typed facts, assumptions, invariants, unknowns, and authority questions. Every fact must cite an allowed file, policy, or tool result. The agent cannot edit source files.

Acceptance:

- unsupported statements remain assumptions;
- safety-relevant unresolved assumptions block world selection or trigger an authority packet;
- output validates against the contract schema.

#### PRD-FR-011: Adversarial Test Designer

The Adversarial Test Designer must choose relevant worlds from the fixed catalog and propose bounded parameters or adversarial sequences. It cannot edit production migrations or decide the final status.

Acceptance:

- every selected world names the threatened invariant;
- generated parameters stay within policy and runtime limits;
- deterministic code compiles the plan before execution.

#### PRD-FR-012: Remediation Engineer

The Remediation Engineer runs only after `BLOCKED` or after a valid domain ruling. It proposes the smallest correction and a regression check. It cannot remove oracle tests, relax policy, or rewrite existing evidence.

Acceptance:

- the original candidate remains immutable;
- correction diff and rationale are captured;
- a clean rerun, not the agent's claim, determines the new status.

### 10.3 Human authority

#### PRD-FR-020: Build a ruling packet

When the missing information is a domain fact, the system must present the exact question, affected rows or cases, competing interpretations when applicable, consequence of each, evidence already checked, and the requested reviewer qualification.

#### PRD-FR-021: Compile a ruling into an invariant

A human ruling must record reviewer role, ruling text, scope, source or justification, timestamp, and version. The system must compile it into an executable constraint and rerun affected worlds.

Acceptance:

- a free-form “approve” response is invalid;
- a ruling cannot suppress a deterministic safety failure;
- changing a ruling changes the certificate hash.

### 10.4 Deterministic migration worlds

#### PRD-FR-030: Isolated PostgreSQL runner

Each world must start from a clean PostgreSQL 16 fixture in a restricted Docker network. The runner must apply resource and time limits and preserve logs and database evidence.

#### PRD-FR-031: Tenant and role isolation world

The runner must test positive and negative access for every declared role and tenant. It must inspect active row-level security policies and exercise queries as each role.

#### PRD-FR-032: Money and reconciliation world

The runner must test exact minor-unit conversion, conservation of value, idempotency, unique disbursement identity, and retry behavior without floating-point comparison.

#### PRD-FR-033: Rolling compatibility world

The runner must interleave old-application and new-application reads and writes across expand, backfill, verify, and contract stages.

#### PRD-FR-034: Interruption and resume world

The runner must inject a bounded failure during backfill, restart it, and prove that resumption neither loses nor duplicates effects.

#### PRD-FR-035: Concurrent write and rollback world

The runner must add writes after migration start, exercise rollback, and compare the final records and audit history with the declared invariants.

#### PRD-FR-036: Lock and availability world

The runner must measure blocking operations against the case policy. A lock over the blocking threshold fails even if the final schema is correct.

#### PRD-FR-037: Audit-history world

The runner must prove required audit events remain present, append-only, attributable, and tenant-scoped.

Acceptance for PRD-FR-030 through PRD-FR-037:

- checks return structured results with command, duration, status, evidence reference, and blocking class;
- a timeout returns `EVIDENCE_INCOMPLETE`, not a pass;
- the same golden inputs produce the same semantic results on three replay runs.

### 10.5 Decision, correction, and blast radius

#### PRD-FR-040: Deterministic decision policy

Code must decide the external state from structured check results. Agent text is never an input that can turn a failed blocking check into a pass.

Decision precedence:

1. A sandbox, trace, replay, or required-world failure produces `EVIDENCE_INCOMPLETE`.
2. A confirmed blocking invariant produces `BLOCKED`.
3. An unresolved material authority question produces `DOMAIN_RULING_REQUIRED`.
4. Otherwise the result is `READY_FOR_REVIEW`.

#### PRD-FR-041: Confirmed blast radius

The blast-radius module must report only impacts supported by executed evidence. Each finding names affected tenants, roles, rows, values, application versions, or availability window when known. Hypothetical impact must be labeled separately.

#### PRD-FR-042: Bounded correction loop

The product may attempt at most one remediation cycle in the headline demo and a configurable bounded number in evaluation. Exhausted budget returns `EVIDENCE_INCOMPLETE` with the best available evidence.

### 10.6 Trace and evidence

#### PRD-FR-050: Observable agent-use trajectory

Every agent must have a representative trajectory from instruction to final output. The trace must record messages sent to the model, structured responses, tool requests, tool results, retries, state transitions, human rulings, timing, token counts when available, cost estimate, and artifact references.

The trace must not record hidden chain-of-thought. It may record concise agent-authored rationales intended for the user.

#### PRD-FR-051: Mediated tools

All file reads, searches, SQL execution, tests, diffs, and sandbox commands requested by agents must pass through a typed tool router with allowlists, timeouts, output caps, and redaction.

#### PRD-FR-052: Trace integrity and privacy

Events must be append-only JSONL with monotonic sequence numbers and a SHA-256 content chain. Secrets, provider keys, host paths outside the fixture, and evaluator-only oracle contents must be removed or replaced with stable references.

#### PRD-FR-053: Readable trace compiler

The system must compile raw trace events into `trajectory.md` and a section of the static certificate. It must make this sequence easy to inspect:

`initial assumption -> test or tool result -> failed expectation -> agent correction -> verified result`

### 10.7 Migration Change Certificate

#### PRD-FR-060: Generate the certificate

Each completed run must emit `certificate.json`, `certificate.md`, and `certificate.html` from the same typed data model.

The first screen must show:

- external state;
- candidate change;
- failed or decisive invariant;
- confirmed blast radius;
- required next action;
- human ruling, if one exists;
- replay command.

Detail sections must show the contract, executed worlds, correction, verification results, trace narrative, runtime and cost, known limits, artifact hashes, and environment.

#### PRD-FR-061: Replay the certificate

Offline replay must verify input and artifact hashes, rerun deterministic checks, compare semantic results, and report any mismatch. It must not call an LLM.

### 10.8 Evaluation and reporting

#### PRD-FR-070: Run the fixed paired experiment

The evaluator must run the same 12 cases in baseline and final conditions. The preferred protocol is 12 cases by 2 conditions by 3 repeats, for 72 runs. If time or provider budget prevents this, it must run all 12 once and repeat C01, C04, C08, and C12 three times.

#### PRD-FR-071: Compute the primary metric

`unsafe_migration_escape_rate = known_unsafe_candidates_marked_ready / all_known_unsafe_candidates`

For the final workflow, `READY_FOR_REVIEW` counts as marked ready. For the baseline, `approve` counts as marked ready. `EVIDENCE_INCOMPLETE` does not count as safe; it is reported separately.

#### PRD-FR-072: Report guardrails

The report must include:

- safe-candidate acceptance on C11 and C12;
- correct authority escalation on C04;
- clean replay rate;
- runtime, token use, and estimated cost;
- timeouts, invalid runs, and integrity failures;
- per-case results as well as aggregate values.

#### PRD-FR-073: Maintain the improvement changelog

Each material iteration must record the hypothesis, change, evidence, decision, and linked artifacts. Planned experiment stages are:

| Stage | Change under test                                                         |
| ----- | ------------------------------------------------------------------------- |
| B0    | Direct agent review                                                       |
| E1    | Equal-budget self-review                                                  |
| E2    | Typed Migration Contract                                                  |
| E3    | Tenant and row-level-security world                                       |
| E4    | Rolling, interruption, and rollback worlds                                |
| E5    | Authority-aware human gate                                                |
| E6    | Targeted mutation or agent debate, retained only if evidence justifies it |
| Final | Smallest retained combination that produces the best defensible result    |

At least one experiment must be removed and explained in the final submission. The reason must come from measured evidence, cost, reliability, or scope, not taste alone.

## 11. Non-functional requirements

### PRD-NFR-001: Reproducibility

The clean judge path is:

```bash
make bootstrap
make test
make baseline
make evaluate
make replay
```

The README must state expected files, approximate runtime, provider requirements, and the difference between offline golden replay and optional live evaluation.

All five commands must work with provider variables unset. `make baseline` validates the committed baseline trajectories and decisions. `make evaluate` recomputes the comparison from committed raw run records and verifies their manifests. Separate commands with a `-live` suffix may regenerate model-dependent runs.

### PRD-NFR-002: Safety

Untrusted migrations run only in disposable containers with no host credentials, no production connection, a restricted network, a non-root user, resource limits, and explicit mounted paths.

### PRD-NFR-003: Determinism

Seeds, time zone, locale, database image, schema, policies, prompt versions, and check ordering must be pinned. Semantic output comparison must ignore only declared volatile fields such as timestamps and measured durations.

### PRD-NFR-004: Performance

The headline C01 demo should finish within 90 seconds after images and dependencies are warm. Each world has a hard timeout. The full evaluation must publish its measured wall time.

### PRD-NFR-005: Usability

A judge should understand the certificate's decision and next action within 20 seconds. The main replay command must be visible without scrolling in the default HTML viewport.

### PRD-NFR-006: Maintainability

Agent prompts, policies, schemas, world definitions, and evaluator oracles must be versioned separately. Deterministic checks must have unit and integration tests independent of model calls.

## 12. Required artifact contract

Each run directory contains:

```text
runs/<run_id>/
  run.json
  inputs/
    case.yaml
    candidate.sql
    policy.yaml
  contract.json
  world-plan.json
  checks.json
  decision.json
  remediation.diff
  ruling.json
  trajectory.jsonl
  trajectory.md
  metrics.json
  environment.json
  manifest.json
  certificate.json
  certificate.md
  certificate.html
  replay.log
```

Files that do not apply, such as `ruling.json`, must be absent or explicitly marked not applicable. They must not contain empty claims.

## 13. Error behavior

| Error                         | External state        | Required evidence                     |
| ----------------------------- | --------------------- | ------------------------------------- |
| Invalid case or candidate     | `EVIDENCE_INCOMPLETE` | Validation issues and path            |
| Oracle leaked before decision | `EVIDENCE_INCOMPLETE` | Access event and affected run         |
| Sandbox policy violation      | `EVIDENCE_INCOMPLETE` | Blocked operation and actor           |
| Required world timeout        | `EVIDENCE_INCOMPLETE` | Timeout, partial logs, retry count    |
| Trace write or hash failure   | `EVIDENCE_INCOMPLETE` | Last valid sequence and storage error |
| Replay mismatch               | `EVIDENCE_INCOMPLETE` | Expected and observed semantic hashes |
| Agent budget exhausted        | `EVIDENCE_INCOMPLETE` | Consumed budget and pending stage     |

Failures must remain visible in evaluation results. They are not silently retried until a favorable run appears.

## 14. Evaluation targets

These are release targets, not results to claim before measurement:

| Measure                      | Target                                                |
| ---------------------------- | ----------------------------------------------------- |
| Unsafe migration escape rate | 0/9 for final workflow                                |
| Known-good acceptance        | 2/2 for final workflow                                |
| Domain authority handling    | C04 returns `DOMAIN_RULING_REQUIRED` before a ruling  |
| Offline replay               | 12/12 golden certificates reproduce                   |
| Trace coverage               | Every agent and tool event represented in valid JSONL |
| Qualification path           | Five documented commands pass from a clean checkout   |

No submission text may convert a target into a reported result.

## 15. Rubric evidence map

| Criterion                      | Points | Product evidence                                                                                                | PRD anchors                    |
| ------------------------------ | -----: | --------------------------------------------------------------------------------------------------------------- | ------------------------------ |
| Problem and User Value         |     15 | Named platform engineer, migration review bottleneck, actionable certificate                                    | Sections 2, 3, PRD-FR-060      |
| Agent Solution and Engineering |     30 | Three bounded agents, typed workflow, mediated tools, deterministic PostgreSQL worlds, human authority boundary | PRD-FR-010 to 053              |
| End-to-End Quality             |     20 | Candidate intake through decision, correction, certificate, and replay                                          | Section 9, PRD-FR-060 and 061  |
| Measured Improvement           |     15 | Fixed paired 12-case experiment and one primary metric                                                          | Section 8, PRD-FR-070 to 073   |
| Reproducibility                |     15 | Five-command path, pinned environment, offline golden replay, hashes                                            | PRD-NFR-001 to 003, section 12 |
| Hot Take and Insights          |      5 | Timeline thesis tied to observed case and experiment evidence                                                   | Sections 2.3, 10.8, 16         |

## 16. Claim rules

A feature may be described as implemented only if its requirement acceptance checks pass and its release artifact exists. A metric may be spoken only if `results/summary.json` contains its numerator, denominator, run count, and experiment hash.

The presentation must distinguish these words:

- “target” means the desired result before evaluation;
- “observed” means recorded by a frozen experiment;
- “confirmed blast radius” means supported by an executed check;
- “possible impact” means a hypothesis that was not executed;
- “ready for review” means evidence gates passed, not that a migration is approved.

The hot take may be presented as a finding only if at least one recorded unsafe case passes final-schema or visible checks but fails a timeline world. Otherwise it stays a product hypothesis.

## 17. Release gates

### Gate R0: scope and integrity

- The 12-case manifest and oracle separation test are frozen.
- Pre-existing and hackathon-created work are labeled.
- P0 and deferred work match section 6.

### Gate R1: deterministic vertical

- C01 runs from intake through a blocked decision without a model call.
- The row-level-security world identifies the missing policy and affected role or tenant.
- A static certificate and replay log are generated.

### Gate R2: agent workflow

- All three agents produce schema-valid outputs through mediated tools.
- C01 shows an observable failure and bounded correction path.
- C04 produces a valid ruling packet and executable ruling.

### Gate R3: benchmark

- All 12 cases produce expected product states in offline golden mode.
- C11 and C12 are not rejected by policy.
- Timeouts and integrity failures remain visible.

### Gate R4: measured comparison

- The baseline and final workflow run on identical frozen inputs.
- Primary and guardrail metrics include numerator and denominator.
- The changelog links each retained or removed experiment to evidence.

### Gate R5: reproduction

- The five-command path passes from a clean checkout.
- Offline replay makes no provider call.
- Certificate and trace hashes verify.

### Gate R6: submission

- README, reproduction guide, changelog, trajectories, disclosure, results, and five-minute video agree with this PRD.
- Every statement in the video passes the claim rules in section 16.
- One removed experiment and the highest-impact retained change are named.

## 18. Risks and controls

| Risk                                 | Control                                                                         |
| ------------------------------------ | ------------------------------------------------------------------------------- |
| Too many components for three days   | CLI-only P0, three agents, fixed world catalog, static HTML                     |
| Agents read expected answers         | Separate evaluator mount, access logs, integrity failure state                  |
| Product wins by rejecting everything | Two known-good cases and acceptance guardrail                                   |
| Model variance weakens comparison    | Same provider, model, limits, cases, repeats, and published failures            |
| PostgreSQL timing varies by machine  | Conservative lock thresholds, pinned image, repeated runs, measured environment |
| Human gate becomes approval theater  | Authority-only trigger and executable ruling schema                             |
| Certificate becomes a raw log dump   | Fixed first-screen fields and trace summary separate from raw JSONL             |
| Replay requires paid access          | Offline golden artifacts and fake provider adapter                              |
| Demo stalls                          | Recorded deterministic replay and static certificate available as fallback      |
| Hot take outruns evidence            | Section 16 claim lock                                                           |

## 19. Product definition of done

ProofBench is done for this hackathon when a judge can take the same unsafe migration that a fair direct-review agent assessed, watch Migration Court expose the failing deployment world, inspect the confirmed blast radius and any correction, and replay the resulting certificate from a clean environment. The 12-case report must show the actual baseline and final escape rates without hiding failures, timeouts, cost, or safe-case rejections.
