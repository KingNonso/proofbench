# ProofBench five-minute presentation sequence

## 1. Recording rule

Record this presentation only after PRD release gate R6 passes. The script is designed to show implemented work, not planned work.

Before recording:

- open the verified C01 certificate from the submission commit;
- open the C04 ruling packet only if its end-to-end test passes;
- open `results/summary.json` and `results/improvement-changelog.md`;
- run the five judge commands once from a clean checkout;
- replace no number by memory; read the numerator and denominator shown on screen;
- remove any optional line whose claim-lock evidence is absent;
- rehearse to 4 minutes 45 seconds so the exported video stays below five minutes.

## 2. Claim-lock table

This table prevents the video from describing a feature that is only in a plan.

| Spoken claim                                                                | May be used only when                                                                              | PRD reference              | Evidence to show                                    |
| --------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | -------------------------- | --------------------------------------------------- |
| ProofBench reviews AI-written PostgreSQL migrations for a platform engineer | Product copy and certificate name the same user and task                                           | Sections 1 to 4            | README opening and C01 certificate                  |
| Three agents have separate jobs                                             | All three schema-valid trajectories exist                                                          | PRD-FR-010 to 012, Gate R2 | `submission/trace-index.md` and C01 `trajectory.md` |
| Deterministic checks make the decision                                      | Decision policy tests pass and the certificate links decisive checks                               | PRD-FR-030 to 040          | `checks.json`, `decision.json`, test output         |
| The system caught the C01 RLS failure                                       | C01 golden and recorded run both block for the same invariant                                      | PRD-FR-031, Gate R1        | C01 certificate and RLS evidence                    |
| The blast radius is confirmed                                               | The affected tenant, role, or row is derived from executed evidence                                | PRD-FR-041                 | Certificate first screen and query artifact         |
| A human is asked only for domain authority                                  | C04 returns `DOMAIN_RULING_REQUIRED` and a valid ruling compiles into an invariant                 | PRD-FR-020 and 021         | C04 ruling packet and ruling test                   |
| The correction passes on rerun                                              | The corrected candidate starts from a clean fixture and all required checks pass                   | PRD-FR-012 and 042         | Original and corrected hashes, rerun checks         |
| The certificate replays offline                                             | Replay passes with provider variables unset                                                        | PRD-FR-061, Gate R5        | `replay.log` and terminal command                   |
| Final improves unsafe escape rate                                           | Frozen paired experiment exists with full counts                                                   | PRD-FR-070 to 072, Gate R4 | `results/summary.json`                              |
| A named change contributed most                                             | Changelog has an experiment comparison supporting it                                               | PRD-FR-073                 | `results/improvement-changelog.md`                  |
| A named experiment was removed                                              | Removal and reason are recorded with evidence                                                      | PRD-FR-073                 | Same changelog entry                                |
| Timeline correctness is a finding                                           | At least one recorded unsafe case passes visible or final-schema checks and fails a timeline world | PRD section 16             | Per-case result and world evidence                  |

If a row is not unlocked, cut its spoken claim. Do not soften it into an unsupported suggestion.

## 3. Screen setup

Prepare five tabs or windows in this order:

1. one problem slide with the tagline and one timeline diagram;
2. split terminal showing C01 candidate, visible tests, and baseline decision;
3. C01 trace and live or recorded deterministic replay;
4. C01 certificate, with C04 ruling packet beside it if unlocked;
5. result comparison, reproduction commands, and changelog.

Use a large terminal font. Hide notifications, provider keys, local personal paths, and unrelated tabs. Keep the cursor near the next item before recording.

## 4. Timed sequence

| Time         | Purpose                                      | Rubric named                              | Screen                                        |
| ------------ | -------------------------------------------- | ----------------------------------------- | --------------------------------------------- |
| 0:00 to 0:32 | User, problem, consequence, thesis           | Problem and User Value, 15 points         | Problem slide                                 |
| 0:32 to 0:58 | Fair baseline                                | Measured Improvement setup                | C01 and baseline decision                     |
| 0:58 to 1:32 | Agent and deterministic architecture         | Agent Solution and Engineering, 30 points | Workflow diagram and trace index              |
| 1:32 to 2:38 | One realistic C01 execution                  | Agent Solution and Engineering            | Trace, world result, blast radius, correction |
| 2:38 to 3:02 | Qualified human boundary                     | Agent Solution and Engineering            | C04 ruling packet                             |
| 3:02 to 3:32 | Finished user artifact                       | End-to-End Quality, 20 points             | C01 certificate                               |
| 3:32 to 4:02 | Paired measured result                       | Measured Improvement, 15 points           | Comparison report                             |
| 4:02 to 4:27 | Clean judge path                             | Reproducibility, 15 points                | Five commands and replay log                  |
| 4:27 to 4:47 | Highest-impact change and removed experiment | Changelog requirement                     | Improvement changelog                         |
| 4:47 to 5:00 | Evidence-backed thesis and close             | Hot Take and Insights, 5 points           | Final slide                                   |

## 5. Spoken script and actions

### 0:00 to 0:32: problem and user value

Show: the title, tagline, staff platform engineer, and a simple deployment timeline.

Say:

> ProofBench Migration Court is the pre-merge trial for AI-written database migrations. It is built for the platform engineer who receives SQL that looks correct and passes visible tests, but still has to prove it will not leak one tenant's data, duplicate a payment, break an old application version, or lose writes on rollback. That is my Problem and User Value: the hard part is not producing SQL. It is deciding whether the deployment timeline is safe enough for human review.

Point to:

- “AI-written candidate” at the start of the timeline;
- “rolling versions,” “interruption,” and “rollback” in the middle;
- “Migration Change Certificate” at the end.

PRD tags: sections 1, 2.1, 2.2, and 3.1.

### 0:32 to 0:58: fair baseline

Show: C01 candidate recreating `payments`, the passing visible schema test, and the direct-review baseline decision.

Say:

> This is C01 from a 12-case frozen benchmark. The migration recreates the payments table but does not restore row-level security. The visible final-schema test passes. The baseline is a fair direct review: one general-purpose agent gets the same candidate, repository, tests, model family, and budget as the final system. Here is its recorded decision and trace.

On screen, highlight the exact baseline decision. Do not say it approved unless the recorded run says `approve`.

PRD tags: PRD-FR-002 and section 8.2.

### 0:58 to 1:32: agent solution and engineering

Show: the three agents above the deterministic world runner. Keep the decision engine visually separate.

Say:

> For Agent Solution and Engineering, I used three agents with narrow jobs. The Contract Analyst separates facts from assumptions. The Adversarial Test Designer selects attacks from a bounded world catalog. The Remediation Engineer can propose a minimal correction only after evidence blocks a candidate. None of them can mark a migration ready. Typed Python code runs PostgreSQL worlds and applies the decision policy. All file, SQL, and process tools are mediated and traced.

Point to each agent once, then point to “deterministic decision.”

PRD tags: PRD-FR-010 to 012, PRD-FR-030, PRD-FR-040, and PRD-FR-051.

### 1:32 to 2:38: realistic C01 execution

Show: the compiled trace or terminal replay. Move through four events only.

Say:

> The Contract Analyst records an assumption that recreating the table preserves its access policy, but it cannot cite evidence. The test designer maps that assumption to the tenant-and-role world. ProofBench creates a clean PostgreSQL database, applies the migration, and queries as each declared role and tenant.

Show the failing result.

> The check fails. A user from one organization can observe rows outside the allowed boundary. The decision engine returns `BLOCKED`; it does not ask another model whether the failure sounds serious. The certificate calls this a confirmed blast radius because it links to executed rows and roles.

If the remediation rerun is unlocked, continue:

> The Remediation Engineer restores the missing policy in a separate candidate. ProofBench throws away the first database, reruns from the base fixture, and records the new result without deleting the original failure.

If it is not unlocked, stop after the blocked decision and use the saved time to show the evidence query.

PRD tags: PRD-FR-010, 011, 012, 031, 040 to 042, and 053.

### 2:38 to 3:02: qualified human boundary

This segment is optional. Use it only if the C04 claim-lock row passes.

Show: C04 ruling packet with the exact currency question and affected rows.

Say:

> Human judgment enters at a different boundary. In C04, the code cannot prove that historical payments without a currency field were all USD. ProofBench returns `DOMAIN_RULING_REQUIRED` and shows the qualified reviewer the exact question, affected rows, competing interpretations, and consequence. Their scoped answer becomes a versioned executable invariant. It cannot override a confirmed security or integrity failure.

PRD tags: PRD-FR-020 and 021.

If this segment is cut, add 12 seconds to the certificate and 12 seconds to the result comparison.

### 3:02 to 3:32: end-to-end quality

Show: the first screen of `certificate.html`, then scroll once to the world and trace details.

Say:

> For End-to-End Quality, the user receives one finished artifact, not a chat dump. The Migration Change Certificate shows the state, change, decisive invariant, confirmed blast radius, next action, human ruling when needed, and replay command on the first screen. JSON, Markdown, and HTML come from the same typed record. The detailed sections preserve the contract, checks, correction, cost, limits, and readable trajectory.

PRD tags: PRD-FR-053, 060, and section 12.

### 3:32 to 4:02: measured improvement

Show: `results/comparison.html` or a simple chart that includes counts, not just percentages.

Say:

> For Measured Improvement, I pre-registered 12 migrations and ran the same cases in both conditions. Nine are known unsafe, one requires domain authority, and two are safe controls so rejecting everything cannot win. The primary metric is unsafe migration escape rate.

Read both `unsafe_approved / unsafe_total` cells aloud, baseline first and final second. Then say:

> The safe controls, authority case, timeouts, runtime, and cost are shown beside the headline result.

PRD tags: section 8.2 and PRD-FR-070 to 072.

### 4:02 to 4:27: reproducibility

Show: README quick start and the successful `make replay` output.

Say:

> For Reproducibility, a judge starts from a clean checkout and runs five commands: bootstrap, test, baseline, evaluate, and replay. The baseline and evaluate commands validate committed run evidence; replay reruns the deterministic worlds. Versions, image digest, prompts, policies, seeds, and artifact hashes are recorded. None of these commands calls a model, and replay exits nonzero if the evidence or decision changes. This log came from the submission commit with provider keys unset.

PRD tags: PRD-FR-061, PRD-NFR-001 to 003, and Gate R5.

### 4:27 to 4:47: changelog, contribution, and removed experiment

Show: two highlighted changelog entries. Use the actual highest-impact retained entry and actual removed entry. Read the retained experiment name and measured effect, then the removed experiment name and recorded reason, directly from those rows.

Say:

> The Improvement Changelog connects each iteration to evidence. The two highlighted rows show the change that contributed most and the experiment I removed. That kept the final system smaller and the comparison honest.

Do not assume the RLS world or agent debate is the winner before evaluation.

PRD tag: PRD-FR-073.

### 4:47 to 5:00: hot take and close

Show: the thesis beside one recorded timeline-world failure.

If the claim lock passes, say:

> My Hot Take and Insight is that migration correctness is a property of the deployment timeline, not the final schema. C01 passed its visible schema check and still failed when a second tenant entered the timeline. ProofBench turns that failure into evidence a reviewer can replay.

If the claim lock does not pass, say:

> My product hypothesis is that migration correctness belongs to the deployment timeline rather than the final schema alone. ProofBench is the testable system I built to examine that claim.

PRD tags: sections 2.3 and 16.

Stop. Do not add a general thank-you or feature list after the final line.

## 6. Demo fallback

If a command stalls during recording:

1. cut to the successful recorded terminal output from the submission commit;
2. show the matching run ID in the certificate and replay log;
3. state that the screen is a recorded deterministic replay;
4. do not imply that a cached file is a live run.

The fallback still qualifies because the repository contains the exact replay command and artifacts.

## 7. Final video audit

- [ ] Duration is 5:00 or less.
- [ ] The primary user and bottleneck are spoken in the first 20 seconds.
- [ ] The baseline is shown before the advanced workflow.
- [ ] One candidate is followed from input to certificate.
- [ ] Agent roles and the deterministic decision boundary are clear.
- [ ] A qualified human checkpoint is shown only if implemented.
- [ ] The certificate is readable at normal playback size.
- [ ] The primary metric uses counts and the same fixed cases.
- [ ] The five reproduction commands appear on screen.
- [ ] The highest-impact retained change and one removed experiment come from the changelog.
- [ ] The hot take is labeled as a finding or hypothesis according to PRD section 16.
- [ ] Every spoken claim is unlocked in section 2 of this document.
- [ ] No provider key, personal path, hidden oracle, or private data is visible.
