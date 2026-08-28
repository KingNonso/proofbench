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
