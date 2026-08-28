# Improvement Changelog

The story of how this solution evolved, per hackathon deliverable 01. Every material
iteration gets an entry linking hypothesis, change, evidence, and decision — including the
experiments that were removed and what they taught.

Metric entries may only be filled from `results/summary.json`, with numerator and
denominator. A blank evidence cell means the experiment has not run yet; it is never filled
from expectation.

## Experiment stages

| Stage | Change under test | Evidence | Decision / learning |
| --- | --- | --- | --- |
| B0 | Direct agent review of the candidate migration | pending | pending |
| E1 | Equal-budget self-review | pending | pending |
| E2 | Typed Migration Contract | pending | pending |
| E3 | Tenant and row-level-security world | pending | pending |
| E4 | Rolling, interruption, and rollback worlds | pending | pending |
| E5 | Authority-aware human gate | pending | pending |
| E6 | Targeted mutation or agent debate | pending | pending |
| Final | Smallest retained combination | pending | pending |

---

## Build log

Engineering decisions that changed the plan. Not the experiment record above.

### 2026-08-28 — Phase 0 freeze

- Read the supplied brief (`hackathon-brief.pdf`, SHA-256 `be811a1d…6f94`) and recorded the
  delta against the planning documents in `docs/kickoff-delta.md`. The brief does **not**
  prohibit Docker or PostgreSQL; ground rule 04 requires sandboxing, which the world runner
  provides. Three brief requirements were not covered by the PRD and were added: human time
  per task as a metric row, agent prompts as submission artifacts, and naming one challenging
  case (C12).
- Froze the AidLedger schema, roles, and all twelve case mechanics in
  `docs/aidledger-case-map.md` before writing any case SQL.
  **Finding:** all twelve cases are database-local — none mutates cluster state — which is
  what makes the database-per-world sandbox optimisation viable for the whole benchmark.
- Corrected the presentation filename reference in `implementation-sequence.md` §14.3.

### 2026-08-28 — Scope change: sandbox isolation

**Changed from** `implementation-plan.md` §9.1, which specified one Docker Compose project
per world.

**Changed to** one disposable container per run, with each world getting a fresh database
cloned from an `aidledger_base` template.

**Why.** A Compose project per world costs roughly two seconds of container boot against
roughly a hundred milliseconds for a template clone. Across twelve cases, seven worlds, and
repeated runs, that difference dominates evaluation wall time.

**Isolation contract, because this is a real trade.** PostgreSQL roles and server settings
are cluster-wide, and `CREATE DATABASE ... TEMPLATE` copies database state only. So:
cluster roles are created once at bootstrap and immutable thereafter; candidates run as a
restricted migration owner; roles and server settings are asserted identical before and after
every world; and any world needing cluster mutation or a server restart gets a fresh
container. Recorded here as a scope change rather than left as a silent difference from the
technical plan.

### 2026-08-28 — Deferred: product Dockerfile

The technical plan lists a `Dockerfile`. The sandbox runs the official PostgreSQL image
directly and the CLI runs on the host through `uv`, so nothing imports a product image yet.
Deferred until something needs it, per the scope-discipline rule in `AGENTS.md` §5.

### 2026-08-28 — Slice 1: sandbox, tenant isolation world, decision, and trace

C01 now runs end to end with no model call: intake, restricted sandbox, passing
visible test, failing RLS world, `BLOCKED` decision, confirmed blast radius, and
a validated hash-chained trace. 145 tests pass.

**Fixture correction: the migration role saw zero rows.** `FORCE ROW LEVEL
SECURITY` applies to the table owner too, and the migration role owns these
tables. With no policy naming it, the C01 candidate's `INSERT ... SELECT` copied
**nothing** and the new table came up empty. That is a far worse failure than a
permission error, because it looks like success. Fixed with explicit maintenance
policies in `policies/001_rls.sql` rather than by dropping `FORCE`, so the
maintenance access stays visible where a reviewer will look for it.

**Fixture correction: `GRANT CREATE ON SCHEMA public`.** Since PostgreSQL 15
`PUBLIC` no longer holds it, so the candidate could not create its temporary
table and C01 failed on a permission error instead of the registered RLS defect —
a containment artifact wearing the costume of a real finding.

**Policy schema 1.0 to 1.1: executable probes replace read/write booleans.**
Booleans could not say what a denial should look like. Row-level security denies
by filtering to zero rows while a missing grant raises 42501, so a migration that
dropped a policy entirely and one that kept it looked identical. `RlsProbeSpec`
declares the expected outcome, the expected rows, and the evidence columns.

**Identity: ephemeral credentials, never `SET ROLE`.** `RESET ROLE` restores the
connection-time identity, so probing tenant isolation from a superuser session
would have proved nothing. Every probe is a direct login as the real role under a
per-run generated password, with `scram-sha-256` rather than trust auth.

**Process control: worlds run in a spawned child.** Spawn, not fork, so the child
inherits no administrative connection. The parent owns tracing, the deadline, and
termination, and treats a crashed, hung, or unparseable child as missing evidence
rather than a passing world.

**Deviation: the sandbox network is not `--internal`.** Verified on Docker 27.4:
an internal network silently drops published port mappings — the container starts,
`NetworkSettings.Ports` comes back empty, and the host cannot reach PostgreSQL at
all. Kept: a dedicated network per run and a loopback-only published port. Lost:
network-level egress blocking, which was defence in depth rather than the primary
control. For SQL inside PostgreSQL to reach the network it needs
`COPY ... FROM PROGRAM`, an untrusted language, or an extension such as dblink,
and the restricted migration role is refused all three with a test for each.

**Implementation note: visible tests run through psycopg, not `psql`.** Same
semantics — assertions raise, any error is a failure — and it captures the
SQLSTATE, which is better evidence than an exit code, without copying files into
the container.

**Measured, not assumed** (`results/sandbox-timings.json`, macOS x86_64, image
already local):

| Step | Median | Max |
| --- | ---: | ---: |
| First cached-image container start | 1443 ms | — |
| Warm container start | 1234 ms | 1937 ms |
| Template clone | **38 ms** | 85 ms |
| Candidate apply | 229 ms | 308 ms |
| RLS world | 574 ms | 594 ms |

The template clone is roughly 32x faster than a container start, which is what
makes database-per-world worth its isolation contract across twelve cases and
seven worlds. Cluster roles and settings are fingerprinted before and after every
world; a change voids the evidence.

### 2026-08-28 — Release gate R1 closed: certificate, manifest, and offline replay

C01 now travels from `case.yaml` to a replayable Migration Change Certificate
with no model call. 174 tests pass.

**Oracle isolation is a process boundary, not a path check.** `OracleSpec` uses a
`case_class` enum rather than an `is_unsafe` boolean, because C04 is neither safe
nor unsafe — its correct outcome is that a human is asked, and a boolean cannot
say that. `read_oracle` requires a `ClosedReview`, which only a parent that waited
for the review subprocess can hold; the existence of a decision file is not
authorisation, since product code could write one itself. `product_view` builds a
benchmark copy with the oracle removed, so containment does not depend on the
subprocess behaving. An AST import test walks the graph rather than grepping, so a
re-export cannot slip past, and a string grep backs it up.

**Manifest layering avoids a hash cycle.** Write order is
`certificate.json -> certificate.md/.html -> manifest.json -> bundle-root.txt`.
The certificate links the manifest by path and never by digest; a manifest that
hashed the certificate while the certificate embedded the manifest's hash could
never be verified at all. `replay.log` is excluded from manifest hashes and from
version control, because it is regenerated on every replay.

**Replay verifies before it executes.** If the recorded bytes do not match, the
rerun is skipped and reported as skipped rather than run — a rerun against
unverified bytes would compare the wrong two things and could launder a
difference into a confirmation. Tested against a changed candidate, a changed
policy, a tampered artifact, a rewritten trace event, and a broken bundle root.

**Fixed: confirmed impacts cited every check in their finding.** Each blast-radius
row now cites only the check that observed it. A confirmed impact citing four
checks when one saw it is a bibliography, not traceable evidence.

**Implementation note: `review` is a linear sequence, not a state machine.** With
one world and no agents there are no branches worth a transition table, and a
state machine built before it has states to hold would be scaffolding rather than
structure. It becomes one when remediation and the authority path arrive.

Gate R1 evidence: `tests/golden/C01/` holds the committed bundle, `make replay`
reproduces it with provider variables unset, and the first HTML viewport carries
all seven PRD-FR-060 fields including the replay command.

### 2026-08-28 — Release gate R2 closed: three agents, bounded correction, human authority

211 tests pass. C01 and C04 both run end to end with no network call.

**The agents cannot decide anything, and that is enforced by the schemas.**
`MigrationContract` has no field for a verdict, `WorldPlan` has no field that
could carry a command, and `RemediationPlan` has no field claiming success. The
separation between the three agents is enforced by per-actor capabilities in the
tool router rather than by instruction: the Contract Analyst cannot execute SQL,
the Test Designer cannot read arbitrary files, and the Remediation Engineer
cannot search the tree. A denied tool call returns a recorded refusal rather than
an empty result, because an agent that cannot tell "denied" from "found nothing"
will build a contract on an absence it never knew about.

**Schema repair stops after one attempt.** A second invalid response ends the
stage as `EVIDENCE_INCOMPLETE` with both responses preserved. Retrying until
something parses selects for parseability, not correctness.

**Fixed: a correction was flipping the decision to READY_FOR_REVIEW.** The
decision is about the candidate that was submitted. Folding a passing correction
into it would let every unsafe candidate reach `READY_FOR_REVIEW` and would make
the PRD-FR-071 escape-rate metric measure nothing at all. The correction is now
its own certificate section, clearly marked as not changing the decision.

**Fixed: deferred worlds were reported as missing evidence.** When an authority
question is open the worlds it governs do not run, because running them would
measure an assumption and report it as a fact. The decision policy read "no world
results" as an evidence failure, so C04 returned `EVIDENCE_INCOMPLETE` instead of
`DOMAIN_RULING_REQUIRED`. The "nothing ran" rule now sits below the authority
check, matching PRD-FR-040 precedence exactly.

**Removed a validator that could never fire.** `Ruling` had a word-list check
rejecting "approved" and similar, but `min_length=20` on `ruling_text` rejected
every one of those first. What actually makes a ruling a ruling is structural:
scope, determination column, determination value and justification are all
required, so a signature cannot be recorded because there is nowhere to put one.
Dead validation is worse than none — it looks like protection.

**The authority gate is a question, not a veto.** Two rulings on the same C04
question reach opposite states: `currency-uniformly-usd.yaml` lets the candidate
through, `currency-per-organisation.yaml` blocks it on `INV-MONEY-002`. Neither
can override a deterministic failure, because decision precedence puts a
confirmed blocking finding above any authority question.

**Replay now mirrors the recorded run.** It re-runs the worlds that actually
produced results, re-applies the recorded ruling, and re-asks the recorded
authority question. It previously assumed every run executed the RLS world, which
made C04 — a run that deliberately executed none — fail to reproduce. A replay
that runs a different plan is comparing two experiments and calling agreement a
reproduction.

**Caught by our own defence-in-depth test.** The string grep behind the AST
oracle check found two product modules spelling `evaluator_only` as a literal
instead of importing `ORACLE_DIR_NAME`. Both now use the constant.

Gate R2 evidence: `tests/golden/C01` carries `contract.json`, `world-plan.json`
and `remediation.json`; `tests/golden/C04` carries `ruling-packet.json` and
`ruling-packet.md`.

### 2026-08-28 — Release gate R3 closed: all twelve cases, all seven worlds

227 tests pass. Every case reaches its registered state and every golden
certificate reproduces offline.

**One shared policy instead of twelve copies.** Per-case policies would drift: a
probe fixed in one case and not another would make two cases disagree about what
the tenant boundary is, and the benchmark would be measuring its own
inconsistency. Cases differ in their candidate and their required worlds, not in
what the system is supposed to guarantee.

**Redesigned the lock world, because the first design was wrong.** It held a
conflicting lock and asserted SQLSTATE 55P03 — which condemned the *correct*
migration too, since every `ALTER TABLE` blocks behind an open reader. The
discriminating fact is not whether a statement takes an exclusive lock but
whether it rewrites the table, and PostgreSQL reports that exactly as a changed
relation filenode. That is identical on every machine and independent of fixture
size, which a stopwatch could never be. C07 rewrites; C12 does not.

**A rollback that cannot run is a finding, not an evidence failure.** C08's
rollback initially died on a foreign key, and the world reported it as broken
machinery. The rollback script is the artifact under test: if it raises, that is
a finding about the candidate, and the worst kind, because nobody discovers it
until they already needed it. The world now distinguishes a failing rollback
script from a failure to reach the database.

**The post-migration write had to become per-case.** The rollback world wrote a
hardcoded payment, which violated the NOT NULL column C08's migration had just
added. A realistic write uses the schema the migration just produced, so it is
declared per case.

**C04 cannot be caught without the agents, and that is correct.** Run with
`--no-agents`, C04 reaches `READY_FOR_REVIEW`: no deterministic check can fail,
because every amount is preserved and every constraint holds. Recognising that a
business fact is unknowable requires the Contract Analyst. The deterministic path
is a reduced mode, not the whole product.

**Every unsafe candidate passes its own visible test.** That was designed, and
each case was checked for it. A case whose defect the obvious check already
catches would not be testing anything the deployment timeline adds.

New worlds: `rolling` runs each live version's declared statements; `interruption`
re-runs the backfill, which is what a resumed deploy does; `rollback` commits a
write and then rolls back; `locks` compares relation filenodes; `audit` compares
recorded events by id and content. `money` gained duplicate-settlement detection,
because the unique constraint on (org_id, idempotency_key) is satisfied by a retry
that mints a fresh key while paying the beneficiary twice.

### 2026-08-28 — Release gate R4 closed: the paired experiment

239 tests pass. The measured result, from `results/summary.json`: the
visible-tests baseline escapes **9/9** unsafe migrations, ProofBench escapes
**0/9**, and both accept **2/2** safe controls.

**Found a bug that would have inflated the result.** C04's visible test declared
a PL/pgSQL variable named `is_nullable`, shadowing the `information_schema`
column of the same name. The test errored with "column reference is ambiguous"
rather than passing — so the baseline rejected C04 for a reason that had nothing
to do with the migration. Every case now has a test asserting its visible test
passes, because the whole benchmark rests on that premise: a case whose defect
the obvious check already catches is not testing what the deployment timeline
adds.

**The baseline is the manual process, and it is a real measurement.** Running the
checks already in CI and merging if they pass is one of the baseline forms the
brief names, it needs no key, and its 9/9 is observed rather than stipulated. The
direct-review agent baseline from PRD-FR-002 is implemented — prompt, adapter and
arm — but is deliberately **not run**: authoring a baseline's answers would be the
easiest way in this repository to fake a result, and `results/comparison.md` says
so in the report itself rather than in a footnote.

**`summary.json` has to follow from `raw-runs.jsonl`.** `make evaluate`
recomputes every numerator and denominator from the raw records and fails if they
disagree, so a number in the submission cannot drift from the runs it came from.
No rate is reported without its denominator, and `EVIDENCE_INCOMPLETE` gets its
own column rather than being folded into either side.

**Human time per task is not measured, and is recorded as not measured.** The
brief asks for it; a number nobody timed would be worse than an absence.

The improvement changelog (`results/improvement-changelog.md`) records three
removed experiments with the evidence that removed them: the lock world's
contention design (failed the correct migration), folding a passing correction
into the decision (made the primary metric meaningless), and an unreachable
`Ruling` validator.

