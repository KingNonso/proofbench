# Engineering review of Claude's ProofBench scaffold plan

## Verdict

Claude's plan has the right first milestone, but it is not ready to execute unchanged.

Start coding after the P0 corrections in this document are folded into the working sequence. The main idea stays the same: build a zero-model C01 path from `case.yaml` to `BLOCKED`, then produce a certificate that replays from a fresh PostgreSQL sandbox.

The changes below reduce empty scaffolding, make the oracle boundary physical, state the real PostgreSQL isolation boundary, anchor trace integrity, and close several test gaps.

## Source facts checked

The final challenge brief is available as `hackathon-brief.pdf`, SHA-256:

```text
be811a1d09ebedef2fc853544132b287924fd0f76d04301ea554b4c7e2d88fc4
```

It does not prohibit Docker or PostgreSQL. It says consequential actions must run in a sandbox or simulation, a qualified human must remain in consequential workflows, synthetic data is acceptable, and every claim must link to evidence. Docker supports that rule rather than conflicting with it.

The local toolchain was checked on 2026-08-28:

| Tool | Observed value |
|---|---|
| `uv` | 0.9.7 |
| Host `python3` | 3.9.6, not 3.11.9 |
| Docker CLI and server | 27.4.0 |
| Docker Compose | v2.31.0 |
| Docker host architecture | `aarch64` |
| GNU Make | 3.81 |
| Git repository | Not initialized |

`make bootstrap` must install Python 3.12 explicitly through `uv`. It cannot rely on the host interpreter.

## What Claude got right

Keep these decisions:

- C01 is the first executable vertical.
- Slice 1 makes zero model calls.
- Product states, errors, hashes, and path safety come before agents.
- A fair direct-review baseline remains separate from the advanced workflow.
- `FakeProvider` is the only provider needed before Gate R1.
- `PolicySpec`, `OracleSpec`, and `run_kind` need explicit contracts.
- Lock checks should use PostgreSQL behavior and SQLSTATE rather than measured milliseconds.
- One semantic-normalization definition must serve replay and golden tests.
- The 12 cases need a shared AidLedger schema before case SQL is written.
- The final judge path must work with provider variables unset.

## P0 changes before coding

### 1. Complete Phase 0 before the scaffold

Claude places the brief review after part of the typed spine. Reverse that order.

Create populated documents before source code:

1. `docs/kickoff-delta.md`
2. `docs/aidledger-case-map.md`
3. `docs/provenance.md`

`docs/kickoff-delta.md` must record the brief filename, SHA-256, rules that affect the architecture, and any differences from the four planning documents. It must not be an empty heading stub.

`docs/aidledger-case-map.md` replaces the proposed “on paper” sketch. For C01 through C12, record:

- table and column involved;
- database role involved;
- required migration world;
- visible test;
- evaluator oracle;
- expected product state;
- expected blast-radius evidence;
- whether the case changes database-level or cluster-level state.

This artifact is the design check that prevents the schema from being rebuilt halfway through the benchmark.

### 2. Correct the provenance claim

Do not describe the four planning documents as “pre-hackathon” based only on the fact that they existed before code.

Their local modification times are between 19:54 and 19:56 WAT on 2026-08-28, after the listed 16:00 WAT kickoff. Unless an earlier source can be shown, classify them as hackathon-created planning work.

Use two initial commits:

1. Commit the four planning documents and the populated Phase 0 evidence as the implementation baseline.
2. Commit the working scaffold and typed validation slice separately.

The first commit can prove “before implementation.” It cannot retroactively prove “before the competition.”

Every commit must follow the workspace Lore commit format.

### 3. Do not create one-line source stubs for the full architecture

The proposed tree creates dozens of files that do no work. That raises review cost, makes coverage look worse, and can make the project appear less finished.

The architecture is already documented in `implementation-plan.md`. Create a source module only when the current slice imports it.

The first scaffold needs only:

```text
src/proofbench/
  __init__.py
  cli.py
  config.py
  errors.py
  domain/
    case.py
    decision.py
    evidence.py
    trace.py
    certificate.py
  intake/
    loader.py
    paths.py
    yaml.py
  sandbox/
    postgres.py
  worlds/
    base.py
    rls.py
  decision/
    policy.py
    blast_radius.py
  tracing/
    hashes.py
    writer.py
    validator.py
  certificate/
    compiler.py
    replay.py
    templates/
      certificate.md.j2
      certificate.html.j2
```

Add agents, provider adapters, the tool router, evaluation modules, and the other worlds when their slice begins.

### 4. Expose only working CLI commands

Do not register commands that exit with “not implemented in this slice.” A judge-facing CLI should not advertise dead paths.

At the end of the scaffold pass, expose only:

```text
proofbench --help
proofbench case validate <case.yaml>
```

At Gate R1, add:

```text
proofbench review <case.yaml>
proofbench trace validate <trajectory.jsonl>
proofbench certificate verify <certificate.json>
proofbench replay <certificate.json>
```

Release Make targets may exist from day one, but unfinished targets must exit nonzero with a stable `EVIDENCE_NOT_BUILT` message. They must never pass as no-ops.

### 5. Split data validation from filesystem access

`CaseSpec` should validate data. It should not resolve paths or read files inside Pydantic validators.

Use this boundary:

```text
YAML bytes
  -> strict YAML loader
  -> CaseSpec and PolicySpec
  -> CaseLoader with explicit case_root
  -> resolved, contained input paths
  -> frozen input hashes
```

Store repository-relative POSIX paths in the schema. Resolve them in `CaseLoader` after validation. The loader must reject:

- absolute paths;
- `..` traversal;
- symlink escapes;
- paths under `evaluator_only`;
- files that change between validation and hashing;
- files above the configured size limit.

The YAML loader must reject duplicate keys and cap document size and alias expansion. A normal safe loader can silently replace a duplicate field, which is unacceptable for policies and case manifests.

### 6. Make the oracle boundary a process boundary

Claude's proposed sentinel, denylist, `OracleReader`, and CI grep are useful defenses, but they are not the primary security boundary.

Use this flow:

```text
evaluation process
  |
  | launches with product-only benchmark mount
  v
proofbench review subprocess
  |
  | writes closed decision + public artifacts
  v
subprocess exits
  |
  | evaluator receives oracle mount/read capability
  v
evaluation process reads OracleSpec and scores the decision
```

Rules:

- `proofbench review` receives no oracle path and no oracle file descriptor.
- The agent-visible and product-visible benchmark copy excludes `evaluator_only`.
- Only `proofbench.evaluation` may import the oracle loader.
- The evaluator reads the oracle after the review subprocess exits and its decision is immutable.
- Oracle access belongs to an evaluator log, not the product trajectory.
- A test scans imports through Python's AST. A string grep remains defense in depth.

The existence of `decision.json` is not sufficient authorization. Product code could create that file itself.

### 7. Keep database-per-world only with an isolation contract

One PostgreSQL container per run with a template database per world is a useful speed optimization. It is not complete isolation.

PostgreSQL roles are cluster-wide. Server settings and some locks also cross database boundaries. `CREATE DATABASE ... TEMPLATE` copies database state, not the whole cluster.

Use a tiered sandbox:

```text
one case run
  |
  +-- one disposable PostgreSQL container
        |
        +-- immutable cluster roles created by bootstrap
        +-- aidledger_base template database
        +-- world_<id> database cloned for database-local worlds
        +-- fresh container for any world that needs cluster mutation or restart
```

Controls:

- Bootstrap roles with the container administrator, then run candidate SQL as a non-superuser migration owner.
- The migration role must not have `SUPERUSER`, `CREATEROLE`, `CREATEDB`, `REPLICATION`, `BYPASSRLS`, or server-file roles.
- Deny or prove failure for `ALTER SYSTEM`, `CREATE ROLE`, `CREATE TABLESPACE`, `COPY ... PROGRAM`, server-file reads, untrusted languages, and unrestricted extension installation.
- Keep roles immutable during database-per-world tests.
- Prefix database and application names by run ID.
- Assert that roles, role settings, and server settings are identical before and after every world.
- Use a new container for a world that changes cluster state or requires server restart.

`CREATE DATABASE ... TEMPLATE` must run outside a transaction and the template must have no active sessions. Treat either failure as `EVIDENCE_INCOMPLETE`.

### 8. Define the lock-world contract precisely

Keep Claude's SQLSTATE direction, with two additions.

The lock test must use two coordinated sessions and an explicit barrier:

```text
session A acquires declared conflicting lock
  -> runner confirms lock in pg_locks
  -> session B sets lock_timeout locally
  -> session B executes candidate statement
  -> runner asserts SQLSTATE 55P03 when policy says the wait is disallowed
```

Use SQLSTATE `55P03` as the decision input. Do not compare localized error text. Record wall time as supporting evidence only.

A passing case also needs a test in which the declared operation completes under the same policy. Otherwise every lock-sensitive statement could be rejected.

### 9. Replace the global volatile-field list with explicit hash projections

A shared `VOLATILE_FIELDS` set is easy to widen until replay stops detecting meaningful differences.

Define two digests:

- raw artifact digest over the exact stored bytes;
- semantic digest over a schema-specific projection.

Each artifact model owns its semantic projection. Volatile fields must be explicit per schema version. The normalizer writes a report listing every omitted or transformed field.

Canonical JSON rules:

- UTF-8;
- sorted object keys;
- compact separators;
- reject NaN and Infinity;
- datetimes normalized to UTC;
- money represented as integer minor units;
- no floats in safety-critical evidence.

Avoid a manifest/certificate hash cycle:

```text
inputs and evidence
  -> certificate.json
  -> certificate.md and certificate.html
  -> manifest.json hashes all prior artifacts
  -> bundle-root.txt contains sha256(manifest.json)
```

The certificate may link to the manifest path. It must not embed a manifest hash that includes the certificate itself.

### 10. Anchor the trajectory and define its failure path

For each `TraceEvent`, compute `current_hash` over the canonical event with `current_hash` omitted and `previous_hash` included. Store the final event hash as `manifest.trace_root_hash`.

The validator must reject:

- malformed or truncated final JSONL;
- missing, duplicate, or decreasing sequence numbers;
- a wrong previous hash;
- an altered event payload;
- an unexpected schema version;
- events after the declared terminal event.

If trace writing fails, write a minimal `failure.json` through an independent atomic temp-file-and-rename path and print the same stable error to stderr. Do not claim the failed trace contains its own failure event. The external state is `EVIDENCE_INCOMPLETE`, and certificate generation must not present the bundle as replay-complete.

### 11. Add minimal Markdown and HTML certificates to Slice 1

Claude defers Markdown and HTML, but Gate R1 in `proofbench-prd.md` requires a static certificate and the presentation depends on the first screen.

Slice 1 should generate unpolished but complete:

- `certificate.json` as the canonical record;
- `certificate.md`;
- `certificate.html` with local CSS and no external assets;
- `manifest.json`;
- `bundle-root.txt`;
- `replay.log`.

Visual polish remains later. The fields and renderer contract do not.

### 12. Build one live trajectory immediately after Gate R1

FakeProvider is correct for Slice 1. It proves deterministic infrastructure and keeps replay free of model access.

The first task after R1 should be one live provider adapter and one real Contract Analyst trajectory for C01. Do this before expanding to every migration world. The hackathon submission requires representative trajectories for every agent, and waiting until the end makes the agent layer look attached rather than load-bearing.

The live adapter must record the public prompt, structured response, tool calls, retries, usage, and cost. It must not record hidden chain-of-thought.

### 13. Build CI as capabilities become real

Do not add six empty or skipped CI jobs in the first commit.

Start with active jobs only:

1. formatting, lint, and mypy;
2. unit and schema tests;
3. C01 PostgreSQL integration and security tests once Slice 1 reaches the sandbox.

Add replay, evaluation, and submission jobs when they have real artifacts to verify. By Gate R6, all six jobs in `implementation-plan.md` must exist and pass.

### 14. Fix the presentation filename reference

`implementation-sequence.md` refers to `proofbench-5-minute-presentation.md`, but the repository file is `5-min-presentation.md`.

Keep the current filename and update the reference before implementation. Do not create a second copy.

## Schema decisions to lock in Slice 1

### Run identity

Do not overload one enum with execution and provider concerns.

```text
run_kind: baseline | migration_court | replay
provider_mode: live | fake | recorded | none
```

Artifact requirements are a discriminated union by `run_kind`. Baseline runs do not require a migration contract or world plan.

### OracleSpec

Use:

```text
schema_version
case_id
case_class: unsafe | safe | authority_required
expected_initial_state
expected_blocking_invariant_ids[]
expected_blast_radius_assertions[]
rationale
```

Avoid a single `is_unsafe` boolean. It cannot describe C04 cleanly.

### CaseSpec and PolicySpec ownership

Avoid duplicating world requirements.

- `CaseSpec` owns case inputs, visible tests, required worlds, optional worlds, seed, and budgets.
- `PolicySpec` owns declared roles, tenant access expectations, blocking classes, lock limits, money rules, and permitted migration capabilities.

### Visible test contract

Use `.sql` files executed with `psql -v ON_ERROR_STOP=1`. A test passes only when the process exits zero. Assertions should raise a database exception on failure. The runner records command, exit code, SQLSTATE when present, capped output, duration, and artifact hash.

This keeps the visible test readable to the baseline agent without adding a second test framework inside the database container.

## Revised scaffold pass

### Files that should be real

- `.python-version`, `.gitignore`, `.editorconfig`, `.env.example`
- `pyproject.toml`, `uv.lock`, `Makefile`, `Dockerfile`, `compose.yaml`
- populated `README.md`, `CHANGELOG.md`, `docs/kickoff-delta.md`, `docs/aidledger-case-map.md`, and `docs/provenance.md`
- minimal source tree from P0 change 3
- C01 `case.yaml`, `policy.yaml`, and validation fixtures
- tests for the typed intake boundary
- CI jobs for static analysis and unit tests

### Files to defer

- empty agent and provider modules;
- empty migration worlds other than RLS;
- empty evaluation reports;
- empty submission indexes;
- live provider adapter;
- GitHub jobs for artifacts that do not exist yet.

### Scaffold acceptance

```bash
make bootstrap
make test
uv run ruff check src tests
uv run mypy src
uv run proofbench --help
uv run proofbench case validate benchmark/aidledger/cases/C01/case.yaml
```

The corrupted-case test should use a pytest temporary file, not a fixed `/tmp/broken-case.yaml` that can collide across runs.

## Revised Slice 1 order

### Step 0: freeze the substrate

- Populate the three Phase 0 documents.
- Resolve the presentation filename.
- Initialize Git and record honest provenance.
- Freeze the AidLedger case map.

### Step 1: minimal executable project

- Pin Python 3.12 with `.python-version`.
- Make bootstrap run `uv python install 3.12`, then `uv sync --frozen` when the lockfile exists.
- Add only working CLI commands.
- Activate static and unit CI.

### Step 2: typed intake and evidence contracts

- Implement the Slice 1 schemas.
- Implement strict YAML loading and contained path resolution.
- Implement raw and semantic hashing.
- Export schema snapshots.

### Step 3: trace and emergency failure sink

- Implement JSONL event writing and validation.
- Anchor the trace root in the manifest contract.
- Implement atomic `failure.json` fallback.

### Step 4: sandbox and AidLedger base

- Start the disposable PostgreSQL container.
- Bootstrap immutable roles and the template database.
- Run candidate SQL as the restricted migration owner.
- Verify the initial semantic hash.
- Add malicious-SQL and cleanup tests.

### Step 5: C01 inputs and oracle

- Create the unsafe candidate.
- Create visible SQL tests that still pass.
- Create evaluator-only `OracleSpec`.
- Prove the product subprocess receives no oracle mount.

### Step 6: RLS world

- Inspect `pg_policies`.
- Execute positive and negative role-by-tenant queries.
- Return a typed `WorldResult`.
- Prove a corrected migration passes the same world.

### Step 7: decision and blast radius

- Apply PRD-FR-040 as a pure function.
- Derive confirmed findings only from executed evidence.
- Return `BLOCKED` for C01 and `EVIDENCE_INCOMPLETE` for missing evidence.

### Step 8: certificate and manifest

- Generate JSON, Markdown, and HTML from one typed certificate.
- Write the final manifest and bundle root without a hash cycle.
- Keep confirmed and possible impact separate.

### Step 9: offline replay

- Verify artifact bytes and schema versions.
- Start a fresh sandbox.
- Rerun the declared world plan.
- Compare semantic digests and decisions.
- Exit nonzero and write a clear replay log on any mismatch.

### Step 10: golden bundle and Gate R1

- Commit the sanitized C01 bundle under `tests/golden/C01`.
- Rerun it with provider variables unset.
- Run the full Slice 1 test matrix.

## Test coverage diagram for Slice 1

No code exists yet, so every path below is a required planned test rather than current coverage.

```text
CASE VALIDATION
==============
case.yaml bytes
  |
  +-- over size or unsafe YAML feature ----------> reject with located validation error
  +-- duplicate key -----------------------------> reject
  +-- schema-invalid ----------------------------> reject with field path
  +-- absolute or traversal path ----------------> reject
  +-- direct or symlink oracle path -------------> reject
  +-- input changes during freeze ---------------> reject as integrity failure
  +-- valid case + policy ------------------------> emit frozen input hashes

C01 REVIEW
==========
frozen C01
  -> start disposable Postgres
     +-- startup/load/hash failure --------------> EVIDENCE_INCOMPLETE + cleanup
     +-- success
          -> run visible tests
             +-- unexpected failure -------------> EVIDENCE_INCOMPLETE
             +-- pass
                  -> apply unsafe candidate as restricted owner
                     +-- privilege escape --------> denied + EVIDENCE_INCOMPLETE
                     +-- timeout/output overflow -> EVIDENCE_INCOMPLETE + cleanup
                     +-- applied
                          -> RLS role x tenant matrix
                             +-- evidence missing -> EVIDENCE_INCOMPLETE
                             +-- cross-tenant row -> BLOCKED + confirmed blast radius
                             +-- corrected case --> READY_FOR_REVIEW

TRACE AND CERTIFICATE
=====================
events
  +-- valid chain -------------------------------> manifest.trace_root_hash
  +-- partial line/order/hash/version error -----> validation failure
  +-- writer failure ----------------------------> atomic failure.json + stderr
decision + evidence
  -> certificate.json
  -> certificate.md and certificate.html
  -> manifest.json
  -> bundle-root.txt

REPLAY
======
bundle
  +-- missing/extra/tampered artifact -----------> nonzero verification failure
  +-- schema version unsupported ---------------> nonzero compatibility failure
  +-- valid bytes
       -> fresh sandbox
       -> rerun RLS world
          +-- same semantic digest and decision -> replay pass
          +-- different evidence or decision ---> replay mismatch, nonzero
```

## Required Slice 1 tests

### Unit

- Exact serialization of the four external states.
- `run_kind` and `provider_mode` discriminators.
- Every valid and invalid Slice 1 schema branch.
- Duplicate YAML keys, oversized YAML, and invalid aliases.
- Raw hash and semantic hash vectors, including Unicode, UTC datetime, and rejected floats.
- Decision precedence truth table.
- Confirmed versus possible blast-radius classification.
- Trace sequence, hash, terminal-event, and truncation checks.
- Manifest layering without circular hashes.
- Stable CLI error-to-exit-code mapping.

### Integration

- Base role access matrix passes before migration.
- C01 visible tests pass.
- C01 RLS world fails with the expected invariant.
- Hand-corrected C01 passes the same world.
- Template clone works only with no active connections.
- Two consecutive world databases have no data leakage.
- Cluster roles and settings are unchanged across worlds.
- Pass, failure, timeout, and cancellation all clean up databases and containers.
- JSON, Markdown, and HTML certificates agree on state and decisive invariant.
- Replay succeeds from a fresh database with provider variables unset.

### Security

- Absolute path, traversal, symlink, and post-validation path swap.
- Any product read under `evaluator_only` fails.
- Product review process starts without an oracle mount or path.
- Candidate cannot create roles, databases, tablespaces, server programs, or server-file access.
- Candidate cannot run as superuser or bypass RLS.
- Statement timeout, output cap, memory limit, and process limit work.
- Trace and certificate redact secrets and private host paths.

### End to end

```text
proofbench review C01
  -> visible checks pass
  -> RLS world finds cross-tenant access
  -> state is BLOCKED
  -> confirmed blast radius is linked to query evidence
  -> static certificate is created
  -> offline replay reaches the same state and semantic digest
```

## Performance review

Database templates are a good candidate optimization, but measure them before depending on them.

Record during Slice 1:

- cold image and container startup;
- warm container startup;
- template database creation median and maximum;
- base fixture load time;
- RLS world time;
- certificate and replay time;
- cleanup time after pass, failure, and timeout.

Run evaluation serially until all 12 cases are deterministic. Add parallel workers only after unique Compose project names, ports, database names, artifact directories, and run IDs are tested. Early parallelism can trade a small wall-time gain for hard-to-debug cross-run contamination.

The PRD target remains a warm C01 demo under 90 seconds. Treat this as a target until measured.

## Failure modes that must be visible

| Failure | Test required | Error handling | User-visible result |
|---|---|---|---|
| Invalid or unsafe case path | Unit and security | Located validation error | Nonzero exit with field and path |
| Oracle exposed to product | Security and E2E | Abort run and invalidate evidence | `EVIDENCE_INCOMPLETE` |
| Candidate requests elevated DB capability | Security | PostgreSQL privilege denial | `EVIDENCE_INCOMPLETE` with denied operation |
| Database start or template clone fails | Integration | Preserve logs and clean up | `EVIDENCE_INCOMPLETE` |
| Required world times out | Integration | Kill session, collect partial evidence, clean up | `EVIDENCE_INCOMPLETE` |
| Trace append fails | Unit fault injection | Atomic fallback file plus stderr | `EVIDENCE_INCOMPLETE` |
| Artifact bytes change | Replay | Hash verification stops before execution | Nonzero replay failure |
| Semantic replay differs | Replay E2E | Write expected and observed digests | Nonzero replay mismatch |
| Cleanup fails | Integration fault injection | Retry bounded cleanup and name leaked resource | Nonzero run with recovery command |

No failure above may end silently.

## NOT in scope for Scaffold and Slice 1

- Contract Analyst, Test Designer, and Remediation Engineer: begin immediately after Gate R1.
- Live provider: first task after R1, not part of the zero-model proof.
- Baseline experiment: it depends on the live provider and fixed C01 input.
- C02 through C12: the case map is required now; executable cases follow R1.
- Money, rolling, interruption, rollback, lock, and audit worlds: their interfaces are shaped by `WorldResult`, but their modules wait.
- Agent tool router: no agent runs in Slice 1.
- Broad mutation testing: retain only if a later experiment improves measured outcomes.
- Hosted API, React viewer, GitHub App, OpenTelemetry, signatures, and distributed workers: deferred by the PRD.
- Package publishing and hosted deployment: the hackathon artifact is a local Docker CLI; document this explicitly rather than implying a public service.

## What already exists

| Existing artifact | Reuse decision |
|---|---|
| `proofbench-prd.md` | Product contract; do not duplicate its requirements in code comments beyond IDs |
| `implementation-plan.md` | Architecture map; this replaces empty module stubs |
| `implementation-sequence.md` | Build-order source after the corrections in this review are applied |
| `5-min-presentation.md` | Presentation contract; fix the one filename reference |
| Final hackathon brief | Record its rules and hash in `docs/kickoff-delta.md` |
| Docker Desktop and Compose | Reuse for local containment |
| `uv` managed Python | Reuse to install and pin Python 3.12 |

There is no existing source code, test framework, Git history, benchmark fixture, or CI pipeline to preserve.

## Engineering review summary

| Review area | Result |
|---|---|
| Scope challenge | Scope reduced from full-tree scaffolding to a Gate R1 vertical |
| Architecture | Six issues: oracle boundary, PostgreSQL isolation, SQL containment, manifest hashing, trace anchoring, and live-agent timing |
| Code quality | Five issues: empty stubs, dead CLI commands, filesystem work in schemas, duplicated ownership, and premature CI jobs |
| Test review | Full Slice 1 path diagram produced; all branches are gaps until code exists |
| Performance | Two issues: unmeasured template optimization and premature parallel evaluation |
| NOT in scope | Written for Scaffold and Slice 1 |
| What already exists | Written and mapped to reuse decisions |
| Separate TODO items | None; all current deferrals are captured in the PRD or this review |
| Critical gaps | Four: physical oracle isolation, restricted SQL execution, trace anchoring, and honest provenance |
| Outside voice | Independent critic and official-document research completed |
| Completeness | Complete fixes recommended for all 14 issues; adoption is pending |

Review status: `ISSUES_OPEN` until the P0 changes become the working implementation plan.

## Final readiness gate

The project is ready to code when these decisions are accepted as the working plan:

- [ ] Phase 0 evidence is populated before source files.
- [ ] Provenance says “pre-implementation” unless earlier pre-hackathon evidence exists.
- [ ] The scaffold is slice-sized, with no broad source stubs.
- [ ] Product CLI exposes only implemented commands.
- [ ] Case loading and path resolution are separate.
- [ ] Oracle data is excluded from the product process, not merely denied by a string check.
- [ ] Database-per-world is limited by an explicit cluster-state isolation contract.
- [ ] Candidate migrations run as a restricted owner with containment tests.
- [ ] Raw and semantic hashes are separate and the manifest has no circular digest.
- [ ] Trace root is anchored in the manifest and trace failure has an independent sink.
- [ ] Slice 1 includes JSON, Markdown, HTML, manifest, bundle root, and replay log.
- [ ] One real live trajectory is the first task after Gate R1.
- [ ] CI contains working jobs only.
- [ ] The presentation filename reference is corrected.

Once these boxes are part of the execution plan, begin with Step 0 and continue through Gate R1 without adding new scope.

## Official technical references

- [PostgreSQL roles are cluster-wide](https://www.postgresql.org/docs/current/sql-createrole.html)
- [PostgreSQL template database behavior and constraints](https://www.postgresql.org/docs/current/manage-ag-templatedbs.html)
- [PostgreSQL extensions are installed in the current database](https://www.postgresql.org/docs/current/sql-createextension.html)
- [PostgreSQL `lock_timeout`](https://www.postgresql.org/docs/current/runtime-config-client.html)
- [PostgreSQL SQLSTATE appendix, including `55P03`](https://www.postgresql.org/docs/current/errcodes-appendix.html)
- [Docker multi-platform manifest lists](https://docs.docker.com/build/building/multi-platform/)
- [Docker image and platform digests](https://docs.docker.com/dhi/explore/security-concepts/digests/)
- [`uv` Python version management](https://docs.astral.sh/uv/concepts/python-versions/)
