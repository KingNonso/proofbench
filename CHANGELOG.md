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
