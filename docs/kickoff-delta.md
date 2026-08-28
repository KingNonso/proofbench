# Kickoff delta

Phase 0 evidence, required by `implementation-sequence.md` §4 and PRD release gate R0.
This document records the final challenge brief, the rules that bear on the architecture,
and every difference between the brief and the four planning documents.

## 1. Brief identity

| Field | Value |
| --- | --- |
| File | `hackathon-brief.pdf` |
| SHA-256 | `be811a1d09ebedef2fc853544132b287924fd0f76d04301ea554b4c7e2d88fc4` |
| Pages | 10 |
| Event | micro1 Agentic Workflows Hackathon |
| Read in full | Yes, 2026-08-28 |

Reproduce the hash with:

```bash
shasum -a 256 hackathon-brief.pdf
```

## 2. Ground rules and their effect on this build

| # | Rule (abridged) | Effect on ProofBench |
| --- | --- | --- |
| 01 | Build with tools and components you already know | No constraint |
| 02 | Make clear what existed before the competition and what you added | See `docs/provenance.md` |
| 03 | Respect licenses and service terms | Dependency inventory kept in `CHANGELOG.md` |
| 04 | Keep consequential actions controlled through a sandbox or simulation; add human approval before the action | **The disposable PostgreSQL sandbox satisfies a rule rather than straining one.** ProofBench never touches a live database and never merges or applies a migration. |
| 05 | Make a qualified human reviewer part of any solution that could significantly affect someone | **Makes the C04 domain-authority path a rule requirement, not an optional feature.** PRD-FR-020 and PRD-FR-021 are therefore mandatory scope. |
| 06 | Choose a legal and ethical use case | Fictional humanitarian cash-assistance domain, no real organisation named |
| 07 | Use public or synthetic data | AidLedger fixtures are wholly synthetic; no private or production data |
| 08 | Keep credentials and private information outside the submission | Redaction tests over traces and certificates; `.env` is git-ignored |
| 09 | Connect every claim about results to submitted evidence | PRD §16 claim rules; `5-min-presentation.md` claim-lock table; README status table |
| 10 | Give judges enough access to run the project and reproduce the main result | Five-command judge path, offline replay, no provider key required |

**No rule prohibits Docker or PostgreSQL.** Rule 04 requires sandboxing or simulation for
consequential actions, which is what the container-based world runner provides. The
contingency in `implementation-sequence.md` §4 ("if PostgreSQL containers are forbidden")
is therefore not triggered.

## 3. Judging rubric

The brief's rubric matches `proofbench-prd.md` §15 exactly. No adjustment required.

| Criterion | Points |
| --- | --- |
| Problem and User Value | 15 |
| Agent Solution and Engineering | 30 |
| End to End Quality | 20 |
| Measured Improvement | 15 |
| Reproducibility | 15 |
| Hot Take / Insights | 5 |
| Total | 100 |

## 4. Required deliverables

| # | Deliverable | Where it lives |
| --- | --- | --- |
| 01 | Complete solution code and Improvement Changelog | Repository, `CHANGELOG.md`, `results/improvement-changelog.md`, `README.md` |
| 02 | Reproduction guide | `REPRODUCTION.md` |
| 03 | Solution video, up to 5 minutes | Recorded from `5-min-presentation.md` |
| 04 | Representative trajectories for every agent | `submission/trace-index.md`, `runs/<run_id>/trajectory.md` |

Deliverable 01 explicitly requires "the code as well as the instructions that shape each
agent". Agent prompts under `src/proofbench/agents/prompts/` are therefore **submission
artifacts**, not internal files, and must be readable and versioned.

## 5. Deltas: brief requirements not already covered by the planning documents

Three additions. None conflicts with the PRD; each extends it.

### D1. Human time per task is a required metric row

The brief's suggested evaluation table has three rows: primary outcome, **human time per
task**, and cost per task. PRD-FR-072 lists runtime, token use, and estimated cost, but not
human time.

**Action:** `results/summary.json` must carry a human-time-per-task figure for both arms —
baseline being reviewer time to reach a decision unaided, final being time to read the
certificate to a decision — or state explicitly why it was not measured. Counts and method
must accompany the figure; an unmeasured estimate may not be presented as an observation.

### D2. Agent instructions are submission artifacts

See section 4. Prompts must ship, be versioned, and be listed in `AGENT_DISCLOSURE.md`.

### D3. One challenging case must be named and explained

The brief asks for "one challenging case and explain what it revealed". The 12-case manifest
satisfies the "ten or more cases" target.

**Action:** `results/comparison.md` nominates **C12** as the challenging case and explains
what it revealed, rather than leaving the reader to infer it from a table.

## 6. Corrections applied to the planning documents

| Issue | Resolution |
| --- | --- |
| `implementation-sequence.md` §14.3 referenced `proofbench-5-minute-presentation.md`; the file is `5-min-presentation.md` | Reference corrected in place; no duplicate file created |

## 7. Phase 0 exit gate S0

| Check | Status |
| --- | --- |
| No final-brief constraint is unresolved | Pass |
| The submission can still use a local PostgreSQL sandbox | Pass, rule 04 supports it |
| P0 scope fits the remaining build window | Pass, scope unchanged from PRD §6.1 |
| Deltas recorded before implementation | Pass, D1 to D3 above |
