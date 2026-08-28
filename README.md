# ProofBench Migration Court

**The pre-merge trial for AI-written database migrations.**

A coding agent hands you a PostgreSQL migration. It looks reasonable and the visible tests
pass. ProofBench answers one question before a human spends an hour on it:

> Is this migration ready for a qualified engineer to review, or is there evidence that it
> must be blocked or clarified first?

---

## Who has this problem

A **staff database or platform engineer** who reviews AI-written schema changes before merge.

## The bottleneck

A final-schema diff does not settle the questions that actually matter:

- Does row-level security still protect every database role?
- Can the old and new application versions both run during a rolling deploy?
- Can an interrupted backfill resume without duplicating money?
- Does rollback preserve writes made after the migration began?
- Does the migration exceed the team's lock-time policy?
- Is a historical data assumption supported, or does a domain owner need to rule on it?

The reviewer either collects this evidence by hand or approves with incomplete evidence. The
first is expensive. The second is how tenants see each other's data.

## Why solving it is valuable

The benchmark models four concrete consequences: cross-tenant data disclosure, duplicate or
incorrect disbursements, lost or mutable audit history, and failed deploys with destructive
rollback. ProofBench turns each into replayable evidence attached to a decision.

---

## What it does

Three bounded agents reconstruct the intended contract, design adversarial migration worlds,
and propose a minimal correction after a failure. **Deterministic PostgreSQL checks make the
safety decision** — agent prose never turns a failed check into a pass.

Every run returns exactly one state:

| State | Meaning | Next action |
| --- | --- | --- |
| `READY_FOR_REVIEW` | All required evidence checks passed. Not an approval. | A qualified engineer reviews the certificate and code |
| `BLOCKED` | A blocking safety invariant failed | Correct the candidate and re-run |
| `DOMAIN_RULING_REQUIRED` | A business fact cannot be derived from allowed evidence | A qualified domain owner records a scoped ruling |
| `EVIDENCE_INCOMPLETE` | Trustworthy evidence could not be produced | Fix the evidence failure and re-run |

Output is a **Migration Change Certificate** in JSON, Markdown, and HTML, replayable offline
without a model call.

---

## Status

Honest build state. Nothing is described as working before its artifact exists
(PRD §16, brief ground rule 09). Updated at the end of every slice.

| Capability | State |
| --- | --- |
| Phase 0 evidence: brief delta, provenance, 12-case map | **Built** |
| Project toolchain, standards, CI (static, unit, docker) | **Built** |
| Typed intake: case and policy schemas, contained path resolution, input hashing | **Built** |
| Disposable PostgreSQL sandbox, restricted migration role, database-per-world | **Built** |
| Tenant isolation world, decision policy, confirmed blast radius | **Built** |
| Trace writer, hash chain, validator, redaction, readable trajectory | **Built** |
| Migration Change Certificate in JSON, Markdown, and HTML | **Built** |
| Manifest, bundle root, and offline replay | **Built** |
| Oracle process boundary and `OracleSpec` | **Built** |
| `case validate`, `review`, `replay`, `trace validate`, `certificate verify` | **Built** |
| Money, rolling, interruption, rollback, lock, and audit worlds | Not built |
| Cases C02 through C12 | Not built |
| Three product agents and live provider | Not built |
| Human authority path (C04 ruling packet) | Not built |
| Fair direct-review baseline and paired evaluation | Not built |

**Release gate R1 is closed.** C01 goes from `case.yaml` to `BLOCKED` with no model
call: the visible schema test passes, the tenant isolation world observes two
Southgate payment rows from a Northwind session, the confirmed blast radius names
role, tenant, operation and row keys, and the certificate replays from a clean
database. `make replay` reproduces the committed golden bundle offline.

`make baseline` and `make evaluate` still exit non-zero with `EVIDENCE_NOT_BUILT`
until there is committed evidence for them to verify. That is deliberate: a
judge-facing command that passes without verifying anything is worse than one
that says why it cannot.

---

## Quick start

Requires Docker and [`uv`](https://docs.astral.sh/uv/). No provider key is needed for any
command below.

```bash
make bootstrap   # install pinned Python 3.12 toolchain, pull the pinned PostgreSQL image
make test        # unit, schema, security, and selected integration tests
make baseline    # validate committed baseline trajectories and decisions
make evaluate    # recompute metrics and verify committed run manifests
make replay      # re-run deterministic checks for committed golden certificates
```

Review a candidate and read its certificate:

```bash
uv run proofbench case validate benchmark/aidledger/cases/C01/case.yaml
uv run proofbench review benchmark/aidledger/cases/C01/case.yaml
uv run proofbench replay tests/golden/C01/certificate.json
uv run proofbench certificate verify tests/golden/C01/certificate.json
uv run proofbench trace validate tests/golden/C01/trajectory.jsonl
```

`review` exits non-zero for a blocked candidate, so it composes with CI. Open
`runs/<run_id>/certificate.html` to read the result.

---

## Repository map

| Path | Contents |
| --- | --- |
| `proofbench-prd.md` | Product contract. The authority for every requirement id |
| `implementation-plan.md` | Technical plan and architecture map |
| `implementation-sequence.md` | Build order and release gates |
| `claude-plan-engineering-review.md` | Engineering review that amended the build order |
| `AGENTS.md` | Engineering standards for anyone working on this repo |
| `docs/` | Phase 0 evidence: kickoff delta, provenance, AidLedger case map |
| `src/proofbench/` | Implementation |
| `benchmark/aidledger/` | Synthetic fixture and the 12 frozen cases |
| `benchmark/aidledger/evaluator_only/` | Oracle. Never readable by product code |
| `tests/` | unit, integration, security, e2e |
| `tests/golden/C01/` | Committed golden bundle that `make replay` reproduces |

---

## Provenance

Nothing here predates the competition. See [`docs/provenance.md`](docs/provenance.md) for
per-artifact labeling, per brief ground rule 02.

## Improvement Changelog

See [`CHANGELOG.md`](CHANGELOG.md). Each material iteration records hypothesis, change,
evidence, and decision — including experiments that were removed.

## Main failure mode

The honest failure mode of this system is **`EVIDENCE_INCOMPLETE`**: a world times out, a
container fails, a trace write breaks, or replay diverges, and ProofBench cannot produce
trustworthy evidence. It reports that state rather than guessing. `EVIDENCE_INCOMPLETE` is
never counted as safe in any metric.

## Hot take

*Hypothesis, not yet a finding.* Under PRD §16 this may be stated as an observation only once
a recorded unsafe case passes its visible and final-schema checks and still fails a timeline
world.

> Migration correctness is a property of the deployment timeline, not the final schema.

## License

MIT.
