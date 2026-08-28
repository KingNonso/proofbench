# Engineering standards

Rules for any AI agent or human working **on** this repository.

Not to be confused with `AGENT_DISCLOSURE.md`, which documents the three *product* agents
that ProofBench itself runs. This file governs how the code gets written; that file
documents what the product does.

`proofbench-prd.md` is the contract. This file is how we keep it.

---

## 1. Non-negotiable invariants

Breaking any of these invalidates evidence, not just code. None may be relaxed to make a
test pass, a demo work, or a deadline.

1. **Product code never reads or mounts `benchmark/aidledger/evaluator_only/`.** Only
   `proofbench.evaluation` may import the oracle loader, and only after a review subprocess
   has exited with its decision closed. A run with earlier oracle access is an integrity
   failure that stays in the result set.
2. **Agent prose never overrides deterministic evidence.** No model output may turn a failed
   blocking check into a pass. The decision is a pure function over typed check results.
3. **Never weaken a check to get a green result.** Do not delete, skip, loosen, or
   special-case a check, oracle, policy, or trace event because it is failing. `BLOCKED` is a
   correct outcome. A benchmark that cannot fail measures nothing.
4. **Untrusted SQL never runs as superuser.** Candidate migrations run as
   `aidledger_migration`, which holds no `SUPERUSER`, `CREATEROLE`, `CREATEDB`,
   `REPLICATION`, or `BYPASSRLS` attribute.
5. **No floating point in the money path.** Amounts are integer minor units end to end.
   Never compare, sum, or convert money through `float`.
6. **No secrets and no host paths in artifacts.** Traces, certificates, and logs are
   redacted. `.env` is never committed.
7. **When evidence cannot be produced, the answer is `EVIDENCE_INCOMPLETE`.** Never a silent
   pass, never a swallowed exception, and never a retry loop that runs until a favourable
   result appears. Timeouts, trace failures, and replay mismatches are product states.

---

## 2. Code standards

- **Python 3.12**, pinned by `.python-version`. Managed with **`uv` only** — never `pip`,
  never a bare `python`. The host interpreter is not a dependency.
- **Pydantic v2** for every persisted or exchanged model, with `extra="forbid"` and a
  `schema_version` field. Unknown fields are rejected, not ignored.
- **Schemas validate data; they do not touch the filesystem.** Path resolution, file reads,
  and hashing happen in a loader that owns a root, after validation.
- **mypy strict** and **ruff** clean. No `# type: ignore` without a reason on the same line.
- **Typed errors** deriving from `ProofBenchError`, each mapped to a stable CLI exit code.
  Exit codes are a public interface; changing one is a breaking change.
- **No `shell=True`.** Subprocesses take argument arrays against an executable allowlist.
- **Sandbox teardown in `finally`.** A cleanup failure is recorded and named; it never erases
  prior evidence.
- **No bare `except`.** Catch what you can handle and re-raise what you cannot.

## 3. Determinism

- Canonical JSON everywhere: UTF-8, sorted keys, compact separators, `NaN` and `Infinity`
  rejected.
- UTC everywhere. Seeded randomness. Pinned image digest, locale, and time zone.
- **No wall-clock value is ever a decision input.** Measure duration and report it as
  evidence; decide on observable facts such as SQLSTATE and lock mode.
- **Volatile fields are declared per schema version**, owned by the model they belong to.
  There is no global volatile-field set — it only ever grows until replay stops detecting
  real differences.
- Two digests, never one: a **raw** digest over stored bytes, and a **semantic** digest over
  a declared projection.

## 4. Testing

- **Every world ships with a known-failing and a known-passing migration.** A world that has
  only ever seen a failure is not known to detect anything.
- **Every visible failure path gets its own test.** Invalid input, oracle exposure, privilege
  escalation, container failure, world timeout, trace write failure, artifact tampering,
  replay mismatch, cleanup failure.
- **Assert on SQLSTATE, never on error text.** Message text is localised and unstable.
- **Use pytest `tmp_path`.** Never a fixed path under `/tmp`.
- Definition of done for a change: targeted `pytest`, then `ruff check`, then `mypy`. Run
  `make test` before any phase exit. Do not mark work complete without running the gate.

## 5. Scope discipline

- **Do not create a module before the slice that imports it.** `implementation-plan.md` §4 is
  the architecture map; empty stubs add nothing to it and make the project read as unfinished.
- **Do not register a CLI command that does not work.** A judge-facing CLI must not advertise
  dead paths. A release target with no evidence exits non-zero with `EVIDENCE_NOT_BUILT`.
- **Do not add a deferred dependency.** FastAPI, LangGraph, React, OpenTelemetry, Redis,
  Celery, and vector databases are out of scope per PRD §6.2.
- Finish the current slice before starting the next. `implementation-sequence.md` §17 lists
  what to cut, in order, if time runs short.

## 6. Claims

- A feature may be described as implemented only when its acceptance checks pass and its
  artifact exists (PRD §16, brief ground rule 09).
- A metric may be stated only from `results/summary.json`, with numerator and denominator.
- "Target" is not "observed". "Possible impact" is not "confirmed blast radius".
- The README status table is part of this rule, not decoration. Update it when a slice lands.

## 7. Commits

Conventional Commits: `type(scope): subject`, imperative mood, with a body explaining why.

```
feat(intake): reject duplicate keys in case YAML

A plain safe-loader silently keeps the last duplicate key. For a policy
file that decides blocking classes, a silently dropped key is a wrong
decision with no error. PRD-FR-001.
```

Reference PRD requirement ids (`PRD-FR-031`) in commit bodies and in code, rather than
restating requirement prose in comments.
