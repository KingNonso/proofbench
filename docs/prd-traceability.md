# PRD traceability

Every requirement in `proofbench-prd.md`, its implementation status, and the
artifact that proves it. Produced by the 2026-08-29 implementation audit and
maintained since; `tests/e2e/test_submission.py` asserts every requirement id in
the PRD appears here, so a requirement cannot silently drop out of this table.

**Status vocabulary.** *Implemented* — acceptance criteria met with a passing
test. *Partial* — implemented with a named limitation. *Deviation (recorded)* —
implemented differently from the PRD's letter, with the change and its reason in
`CHANGELOG.md`. *Not run (key-gated)* — implemented, but producing its evidence
requires a provider key that has not been supplied.

## Functional requirements

| Requirement | Status | Evidence |
| --- | --- | --- |
| PRD-FR-001 validate and freeze the case | Implemented | `intake/loader.py` (frozen input hashes), `manifest.json` per bundle now carries `prompt_hashes` for every agent that ran; `benchmark/aidledger/manifest.yaml` frozen with per-case sha256; `tests/unit/test_loader.py` |
| PRD-FR-002 fair direct-review baseline | **Not run (key-gated)** | Implemented in `evaluation/baseline.py` + `agents/prompts/direct_reviewer_v1.md`; `make evaluate-live` runs it. `results/comparison.md` states the omission in the report itself |
| PRD-FR-010 Contract Analyst | Implemented | `agents/contract_analyst.py`; no verdict field exists on `MigrationContract`; `tests/unit/test_agent_boundaries.py` |
| PRD-FR-011 Adversarial Test Designer | Implemented | `agents/test_designer.py`; plan schema cannot carry a command; invented worlds rejected |
| PRD-FR-012 Remediation Engineer | Implemented | `agents/remediation_engineer.py`; original candidate immutable; clean rerun decides, not the agent; `remediation.diff` captured |
| PRD-FR-020 ruling packet | Partial | `workflow/authority.py` + `domain/ruling.py`; packet carries question, rows by tenant, both readings, consequences, checked evidence, qualification. Limitation: the classifier compiles only the currency question — benchmark-scoped, per PRD §4's narrow claim |
| PRD-FR-021 ruling compiles to an invariant | Implemented | `CompiledRuling` executed by the money world; free-form approval structurally unrepresentable; ruling changes the bundle; cannot suppress a deterministic failure (`tests/e2e/test_c04_authority.py`) |
| PRD-FR-030 isolated PostgreSQL runner | Deviation (recorded) | `sandbox/` — one container per run + database-per-world (38 ms clone vs 1234 ms boot, measured), non-`--internal` network (Docker 27.4 drops published ports). Both in `CHANGELOG.md`; containment tests in `tests/security/` |
| PRD-FR-031 tenant and role world | Implemented | `worlds/rls.py`; both directions probed; C01/C02 failing, base + corrected passing |
| PRD-FR-032 money world | Implemented | `worlds/money.py`; integer minor units, conservation, one settlement per payment, compiled rulings; C03/C09 failing, C11 passing |
| PRD-FR-033 rolling world | Implemented | `worlds/rolling.py`; declared per-version statements; C05 failing, C12 passing |
| PRD-FR-034 interruption world | Implemented | `worlds/interruption.py`; re-runs the backfill; C06 failing, C12 passing |
| PRD-FR-035 rollback world | Implemented | `worlds/rollback.py`; post-start write must survive; a rollback that cannot run is a finding; C08 failing, C12 passing |
| PRD-FR-036 lock world | Deviation (recorded) | `worlds/locks.py`; verdict is `pg_relation_filenode` change + SQLSTATE 55P03, never wall time — the PRD's "lock-time policy" is enforced through a deterministic fact. Original contention design removed with evidence (`results/improvement-changelog.md`) |
| PRD-FR-037 audit world | Implemented | `worlds/audit.py`; before/after by id and content; C10 failing, C12 passing |
| PRD-FR-040 deterministic decision policy | Implemented | `decision/policy.py` pure function; truth table in `tests/unit/test_decision_policy.py`; agent text is not an input |
| PRD-FR-041 confirmed blast radius | Partial | `decision/blast_radius.py`; confirmed items cite the observing check and real row keys. `possible[]` exists, is never merged, and is honestly empty — populating it needs contract-derived hypotheticals, listed in certificate known limits |
| PRD-FR-042 bounded correction loop | Implemented | `review_case(remediation_attempts=…)`, CLI `--remediation-attempts` (default 1, the headline-demo bound); exhausted budget certifies blocked with best evidence |
| PRD-FR-050 observable trajectory | Implemented | `tracing/writer.py`; messages, responses, tools, retries, transitions, timing, tokens; no hidden chain-of-thought |
| PRD-FR-051 mediated tools | Implemented | `tools/router.py`; per-actor allowlists, caps, redaction; denial is recorded, never empty |
| PRD-FR-052 trace integrity and privacy | Implemented | Append-only JSONL, monotonic seq, SHA-256 chain; redaction before hashing; `tests/unit/test_trace.py` |
| PRD-FR-053 readable trace compiler | Implemented | `tracing/compiler.py` → `trajectory.md`; the assumption→check→failure→correction→verified sequence shown in `tests/golden/C01/trajectory.md` |
| PRD-FR-060 certificate | Implemented | One typed record → JSON/MD/HTML; seven first-screen fields above the fold, test-asserted; local assets only |
| PRD-FR-061 offline replay | Implemented | `certificate/replay.py`; verifies before executing; no LLM call possible (SDK absent on the judge path); tamper paths tested |
| PRD-FR-070 fixed paired experiment | Partial | Fallback protocol executed exactly: 12 cases × 2 arms × 1 + C01/C04/C08/C12 ×3 (40 records, repeats identical). The 72-run preferred protocol and the agent arm await a key |
| PRD-FR-071 primary metric | Implemented | `evaluation/records.py`; counts before rates; `EVIDENCE_INCOMPLETE` its own column, never counted safe |
| PRD-FR-072 report guardrails | Implemented | `summary.json`: safe acceptance, authority accuracy, clean replay 12/12, runtime, tokens, cost, per-case CSV; `make evaluate` recomputes all of it |
| PRD-FR-073 improvement changelog | Partial | `results/improvement-changelog.md`; B0 measured, E2–E5 retained with evidence, E6 cut per sequence §17, three removals with evidence. E1 unrun (key-gated) |

## Non-functional requirements

| Requirement | Status | Evidence |
| --- | --- | --- |
| PRD-NFR-001 reproducibility | Implemented | Five commands from a clean clone, 194–203 s measured, provider variables unset; `-live` targets separate |
| PRD-NFR-002 safety | Implemented | Disposable containers, non-root-capability migration role, loopback-only port, resource limits; `tests/security/` |
| PRD-NFR-003 determinism | Partial | Pinned image/seeds/UTC; semantic digests per model; repeats identical across the four repeated cases and both arms. Three-replay stability asserted per-world for RLS, per-bundle once for all twelve |
| PRD-NFR-004 performance | Implemented | C01 warm demo ≈ 15 s (budget 90 s); wall times in `results/sandbox-timings.json` and `summary.json` |
| PRD-NFR-005 usability | Implemented | Verdict-first certificate; replay command above the fold, test-asserted |
| PRD-NFR-006 maintainability | Implemented | Prompts/policies/schemas/worlds/oracles versioned separately; deterministic checks tested without model calls |

## Release gates

| Gate | Status | Evidence |
| --- | --- | --- |
| R0 scope and integrity | Closed | `docs/kickoff-delta.md`, `docs/provenance.md`, frozen manifest with verified hashes |
| R1 deterministic vertical | Closed | C01 blocked without a model call; golden bundle replays |
| R2 agent workflow | Closed | Three schema-valid agents; C01 correction path; C04 packet + executable ruling |
| R3 benchmark | Closed | 12/12 expected states offline; C11/C12 accepted; failures visible |
| R4 measured comparison | Closed, with a named caveat | 9/9 vs 0/9 on identical frozen inputs under the PRD fallback protocol; the *agent* baseline arm is key-gated and disclosed |
| R5 reproduction | Closed | Clean clone, five commands, no key, twice measured |
| R6 submission | Closed except the video | Claim lock executable; all documents present and link-checked; the recording itself is human work |

## Known honest gaps

1. **The direct-review agent baseline has never produced a number** (PRD-FR-002).
   One command away: `uv sync --extra live && make evaluate-live` with a key.
2. **E1 (equal-budget self-review) unrun** for the same reason.
3. **`possible[]` blast radius is always empty** — stated in every certificate's
   known limits rather than silently.
4. **The authority classifier compiles one question type** — the benchmark's;
   generalising it is platform work the PRD's §6.2 defers.
