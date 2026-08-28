# ProofBench Migration Court technical implementation plan

## 1. Purpose

This plan implements the product contract in `proofbench-prd.md`. The hackathon build is a local Python CLI with a disposable PostgreSQL sandbox, three bounded agents, deterministic checks, a static certificate, and an offline replay path.

The implementation should feel smaller than the PRD. Most product value comes from a few clean boundaries:

- the candidate and oracle never share an agent-visible mount;
- agents propose structured work but cannot issue the final decision;
- PostgreSQL worlds return typed evidence;
- one certificate model feeds every output format;
- the same evaluator scores baseline and final runs.

## 2. Architecture at a glance

```text
case.yaml + candidate.sql + policy.yaml
                    |
                    v
          Intake and input hasher
                    |
        +-----------+-----------+
        |                       |
        v                       v
 Direct-review baseline   Migration Contract
                                |
                                v
                       Authority classifier
                         |             |
                    ruling needed      no ruling
                         |             |
                         v             v
                    Human packet   World plan
                                       |
                                       v
                           PostgreSQL world runner
                                       |
                 +---------------------+--------------------+
                 |          |          |         |          |
                RLS       money     rolling   rollback     locks
                 +---------------------+--------------------+
                                       |
                                       v
                    Deterministic decision + blast radius
                                       |
                         +-------------+-------------+
                         |                           |
                       blocked                    ready
                         |
                         v
                  Remediation Engineer
                         |
                         v
                   clean rerun once
                         |
                         v
             Certificate + trajectory + replay bundle
```

The evaluator oracle is outside this workflow. It reads the final decision only after the run closes.

## 3. Technology choices

| Area                  | Choice                                                                  | Reason                                                                 |
| --------------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| Runtime               | Python 3.12                                                             | Strong database, testing, schema, and CLI support                      |
| Package manager       | `uv` with committed lockfile                                            | Fast clean setup and pinned dependencies                               |
| CLI                   | Typer                                                                   | Typed commands and clear help output                                   |
| Schemas               | Pydantic v2                                                             | Strict agent outputs, case files, traces, and certificates             |
| Workflow              | Explicit typed state machine                                            | Easy to inspect and test; no graph framework required for three agents |
| PostgreSQL client     | `psycopg` v3                                                            | Direct PostgreSQL control and transaction support                      |
| Fixture migrations    | SQL files plus a small Python runner                                    | Keeps the benchmark readable and framework-independent                 |
| Testing               | `pytest`, `pytest-xdist` where safe, Hypothesis for targeted properties | Covers deterministic code and bounded adversarial inputs               |
| Sandbox               | Docker Compose with PostgreSQL 16 pinned by digest                      | Database fidelity and clean replay                                     |
| Templates             | Jinja2                                                                  | One typed certificate rendered to Markdown and HTML                    |
| Local metadata        | SQLite through Python standard library                                  | No extra service for run indexing                                      |
| Trace format          | Append-only JSONL plus SHA-256 chain                                    | Easy to inspect, validate, and compile                                 |
| Formatting and checks | Ruff and mypy                                                           | Fast lint, format, and type gates                                      |
| Task runner           | Make                                                                    | Five obvious commands for judges                                       |
| CI                    | GitHub Actions                                                          | Clean-environment test and replay evidence                             |

### 3.1 Deliberate exclusions

Do not add LangGraph unless the explicit state machine becomes unmanageable. Do not add FastAPI, React, OpenTelemetry, Redis, Celery, a vector database, or a hosted service to P0. These dependencies increase setup and test surface without improving the primary metric.

### 3.2 Provider boundary

Define one asynchronous provider interface:

```python
class ModelProvider(Protocol):
    async def complete(self, request: ModelRequest) -> ModelResponse: ...
```

Implement:

- `FakeProvider` for deterministic tests and offline golden replay;
- one live provider adapter selected after the kickoff environment is known.

Provider responses must be parsed into Pydantic models. Invalid output gets one schema-repair attempt. A second failure ends the stage as `EVIDENCE_INCOMPLETE`.

## 4. Repository layout

```text
proofbench/
  pyproject.toml
  uv.lock
  Makefile
  Dockerfile
  compose.yaml
  README.md
  CHANGELOG.md
  REPRODUCTION.md
  AGENT_DISCLOSURE.md
  src/proofbench/
    __init__.py
    cli.py
    config.py
    errors.py
    domain/
      case.py
      contract.py
      decision.py
      evidence.py
      ruling.py
      trace.py
      certificate.py
      metrics.py
    workflow/
      machine.py
      intake.py
      authority.py
      remediation.py
    agents/
      contract_analyst.py
      test_designer.py
      remediation_engineer.py
      prompts/
        contract_analyst_v1.md
        test_designer_v1.md
        remediation_engineer_v1.md
    providers/
      base.py
      fake.py
      live.py
    tools/
      router.py
      file_tools.py
      sql_tools.py
      process_tools.py
      redaction.py
    sandbox/
      docker.py
      postgres.py
      resources.py
    worlds/
      base.py
      rls.py
      money.py
      rolling.py
      interruption.py
      rollback.py
      locks.py
      audit.py
    decision/
      policy.py
      blast_radius.py
    tracing/
      writer.py
      validator.py
      compiler.py
      hashes.py
    certificate/
      compiler.py
      replay.py
      templates/
        certificate.md.j2
        certificate.html.j2
    evaluation/
      runner.py
      oracle.py
      metrics.py
      comparison.py
  benchmark/aidledger/
    schema/
    roles/
    fixtures/
    policies/
    cases/C01/ ... C12/
    manifest.yaml
    evaluator_only/
  schemas/
  tests/
    unit/
    integration/
    security/
    e2e/
    golden/
  results/
  runs/
  submission/
```

`benchmark/aidledger/evaluator_only` must never be mounted into an agent or product container.

## 5. Core schemas

Schemas are versioned with a `schema_version` field. Unknown fields are rejected in agent outputs and case definitions.

### 5.1 CaseSpec

Required fields:

- `case_id`, title, description;
- starting schema and fixture paths;
- candidate migration and optional rollback paths;
- visible test paths;
- policy path;
- allowed agent tools;
- required and optional world names;
- seed and per-stage budgets.

Evaluator labels live in a separate `OracleSpec` file.

### 5.2 MigrationContract

```text
facts[]: statement, evidence_ref
assumptions[]: statement, safety_relevance, evidence_checked[]
invariants[]: id, description, blocking_class, executable_check
unknowns[]: question, owner, materiality
authority_questions[]: question, reviewer_qualification, affected_invariants[]
```

### 5.3 WorldPlan and WorldResult

`WorldPlan` contains a catalog world ID, threatened invariants, bounded parameters, expected evidence, and timeout. It cannot contain free-form shell commands from an agent.

`WorldResult` contains status, started and ended timestamps, semantic result hash, evidence references, measured values, and any blocking findings.

### 5.4 DecisionRecord

Contains external state, policy version, ordered reasons, decisive check IDs, confirmed blast radius, possible impacts, required action, and evidence completeness.

### 5.5 TraceEvent

Required fields:

- run, sequence, event, actor, stage, and parent span IDs;
- event type and timestamp;
- public input and output summaries;
- content-addressed references to full allowed payloads;
- model, tool, token, cost, timing, and retry metadata where applicable;
- previous-event hash and current-event hash;
- redaction list.

### 5.6 MigrationChangeCertificate

Contains the first-screen summary, contract, world results, decision, blast radius, ruling, remediation, verification, trajectory summary, environment, cost, limits, manifest hashes, and replay command.

JSON is canonical. Markdown and HTML are projections of the same model.

## 6. Typed workflow

### 6.1 States

```text
INGEST
  -> CONTRACT
  -> AUTHORITY_CHECK
     -> DOMAIN_RULING_REQUIRED -> APPLY_RULING -> DESIGN_WORLDS
     -> DESIGN_WORLDS
  -> RUN_WORLDS
  -> DECIDE
     -> READY_FOR_REVIEW -> CERTIFY
     -> BLOCKED -> REMEDIATE -> RUN_WORLDS -> DECIDE -> CERTIFY
     -> EVIDENCE_INCOMPLETE -> CERTIFY
  -> COMPLETE
```

The baseline uses `INGEST -> DIRECT_REVIEW -> BASELINE_DECISION -> COMPLETE` and never enters the advanced workflow.

### 6.2 Transition rules

- State transitions are functions over typed inputs.
- Every transition emits `state.entered` and `state.exited` events.
- Only the policy module can enter a terminal product state.
- Remediation can occur once in the demo and never edits the original input.
- A second blocked result is certified as blocked.
- Any required evidence failure moves to `EVIDENCE_INCOMPLETE`.

## 7. Agent implementation

### 7.1 Contract Analyst, PRD-FR-010

Inputs: case description, candidate SQL, allowed repository files, visible tests, and policy.

Tools: read allowed file, search allowed tree, inspect schema, inspect declared roles.

Output: `MigrationContract`.

Hard limits:

- read-only;
- no evaluator files;
- no SQL execution;
- no decision field in its schema.

### 7.2 Adversarial Test Designer, PRD-FR-011

Inputs: validated contract and fixed world catalog.

Tools: read world documentation, query schema metadata from a disposable planning database, inspect visible tests.

Output: `WorldPlan[]`.

Hard limits:

- chooses only catalog worlds;
- can set only schema-defined parameters;
- cannot provide shell, Docker, or arbitrary SQL commands;
- cannot edit the candidate.

### 7.3 Remediation Engineer, PRD-FR-012

Inputs: original candidate, failed checks, contract, and ruling if applicable.

Tools: read evidence, propose file patch, run visible regression checks in the sandbox.

Output: typed remediation plan plus unified diff.

Hard limits:

- cannot edit policies, oracles, trace history, or expected results;
- cannot delete or weaken checks;
- cannot make a product decision;
- correction size and attempts are capped.

## 8. Tool router and containment

Every agent action becomes a typed `ToolRequest`. The router validates actor, current state, tool, path, arguments, timeout, output limit, and cost before execution.

Required controls:

- resolved paths must remain under the case's agent-visible root;
- subprocesses use fixed executable allowlists and argument arrays, never a shell string;
- SQL executes only against the disposable case database;
- Docker containers run as non-root with CPU, memory, process, and wall-time limits;
- network access is restricted to the private Compose network needed for PostgreSQL;
- provider credentials remain in the host adapter and are never mounted;
- stdout and stderr are capped, stored as artifacts, and represented in trace by hashes;
- known secret patterns and absolute host paths are redacted.

Security tests must cover traversal, symlinks, command injection, network calls, secret reads, oracle reads, oversized output, and fork bombs.

## 9. PostgreSQL world runner

### 9.1 Lifecycle

For each world:

1. Create a unique Compose project name.
2. Start PostgreSQL from the pinned image.
3. Apply roles, base schema, policies, and synthetic fixtures.
4. Verify the initial state hash.
5. Start any old or new application simulators required by the world.
6. Apply the candidate in named phases.
7. Inject scheduled writes, failures, retries, or rollback.
8. Run deterministic assertions.
9. Export logs, query results, plans, locks, and semantic hashes.
10. Destroy the project and volume.

Cleanup runs in `finally`. A cleanup failure is recorded but does not erase prior evidence.

### 9.2 World contracts

| World        | Main implementation                                       | Blocking evidence                                 |
| ------------ | --------------------------------------------------------- | ------------------------------------------------- |
| RLS          | Inspect policies and execute role-by-tenant access matrix | Unauthorized row visible or required access lost  |
| Money        | Compare integer minor units and idempotency keys          | Value drift, duplicate effect, or missing value   |
| Rolling      | Interleave v1 and v2 reads/writes                         | Either version cannot preserve declared semantics |
| Interruption | Fail at seeded backfill checkpoint and resume             | Duplicate, loss, or non-repeatable terminal state |
| Rollback     | Write after migration start, then rollback                | New write lost, corrupted, or unreadable          |
| Locks        | Sample blockers and wait duration                         | Declared lock budget exceeded                     |
| Audit        | Compare append-only event set and role access             | Event removed, mutated, unattributed, or leaked   |

Do not use an LLM to judge a query result. Convert each result into a typed assertion.

## 10. Decision and blast radius

Implement the precedence in PRD-FR-040 as a pure function. Unit tests should cover every combination of evidence completeness, blocking result, and authority question.

Blast radius is computed from observed rows and roles. It has two fields:

- `confirmed[]`, derived from executed evidence;
- `possible[]`, derived from contract analysis but not confirmed.

The certificate must not merge them.

## 11. Trajectory system

### 11.1 Event types

Use a small stable vocabulary:

```text
run.started
run.completed
state.entered
state.exited
model.requested
model.responded
model.schema_repair
tool.requested
tool.completed
tool.denied
check.started
check.completed
assumption.recorded
ruling.requested
ruling.recorded
remediation.proposed
decision.recorded
artifact.written
error.recorded
```

### 11.2 Write path

The trace writer assigns sequence numbers, writes one canonical JSON object per line, computes the previous hash and current hash, flushes, and then publishes the event to the in-process compiler. A trace write failure ends the run as `EVIDENCE_INCOMPLETE`.

### 11.3 Trace compiler

The compiler groups events by stage and produces:

- one-page run summary;
- agent instruction and tool timeline;
- assumption-to-evidence chains;
- retries and schema repairs;
- failed result to correction chain;
- human checkpoint record;
- runtime and cost table.

The compiler uses explicit event fields. It does not infer hidden reasoning.

## 12. Certificate and replay

### 12.1 Compiler

Validate a `MigrationChangeCertificate`, serialize canonical JSON with sorted keys, then render Markdown and HTML. The HTML uses local CSS and no remote fonts, scripts, or network assets.

### 12.2 Manifest

`manifest.json` records schema version, run ID, input hashes, output hashes, image digest, Python and PostgreSQL versions, prompt hashes, policy hash, evaluator version, and replay command.

### 12.3 Offline replay

`proofbench replay <certificate.json>` must:

1. verify the manifest and trace chain;
2. confirm all referenced inputs exist and match hashes;
3. start a clean sandbox;
4. rerun the deterministic world plan;
5. recompute the decision;
6. compare normalized semantic results;
7. write `replay.log` and exit nonzero on mismatch.

Fake-provider golden events may reconstruct the agent-stage artifacts, but replay cannot call a live model.

## 13. Evaluation design

### 13.1 Frozen inputs

`benchmark/aidledger/manifest.yaml` lists all 12 cases and hashes. `results/experiment.json` records the chosen protocol, model, prompts, budgets, repeats, host information, commit, and start time before runs begin.

### 13.2 Arms

- Baseline: one direct reviewer agent with the candidate, repository, visible tests, and common budget.
- Final: Migration Court with the same inputs and total agent budget.
- E1 through E6: changelog experiments. They do not replace the two headline arms.

### 13.3 Scoring

The evaluator maps decisions to a common record, then reveals the oracle. It computes:

```text
unsafe_escape_rate = unsafe_approved / unsafe_total
safe_acceptance_rate = safe_marked_ready / safe_total
authority_accuracy = authority_cases_correct / authority_cases_total
clean_replay_rate = replay_passed / replay_attempted
```

Report counts before percentages. Report every timeout, invalid run, and exclusion by case and arm.

### 13.4 Output files

```text
results/
  experiment.json
  raw-runs.jsonl
  per-case.csv
  summary.json
  comparison.md
  comparison.html
  improvement-changelog.md
```

`summary.json` is the only source for video metrics.

## 14. Test plan

### 14.1 Unit tests

- Pydantic schema acceptance and rejection;
- state transition table;
- decision precedence;
- blast-radius classification;
- hash chain and redaction;
- metric numerator and denominator calculations;
- certificate normalization;
- authority ruling validation.

### 14.2 Integration tests

- each world against one known-failing and one known-passing migration;
- Docker startup, fixture load, cleanup, and timeout;
- agent adapter with fake responses and mediated tools;
- certificate compile and semantic replay;
- baseline and final evaluator oracle separation.

### 14.3 Security tests

- path traversal and symlink escape;
- evaluator-only file read;
- shell metacharacter arguments;
- network request from migration;
- environment and credential read;
- excessive output and resource use;
- trace redaction and tamper detection.

### 14.4 End-to-end tests

- C01: unsafe RLS migration is blocked and corrected candidate reruns;
- C04: business ambiguity produces ruling packet, scoped ruling, and rerun;
- C11: simple safe migration reaches `READY_FOR_REVIEW`;
- C12: difficult safe migration passes every required world;
- clean checkout golden replay using the five commands.

### 14.5 Golden artifacts

Commit sanitized golden certificates and traces for C01, C04, C11, and C12. Golden tests compare semantic JSON, not timestamps or HTML whitespace.

## 15. Commands and expected outputs

```bash
make bootstrap  # installs locked dependencies and pulls the pinned database image
make test       # runs unit, schema, security, and selected integration tests
make baseline   # validates committed baseline trajectories and decisions
make evaluate   # recomputes metrics and verifies committed run manifests
make replay     # reruns deterministic checks for committed golden certificates
```

These five targets must work with provider variables unset. Live experiment generation uses explicit `make baseline-live` and `make evaluate-live` targets. The `-live` targets are evidence-production tools, not part of the clean judge path.

Additional developer commands:

```bash
uv run proofbench case validate benchmark/aidledger/manifest.yaml
uv run proofbench review benchmark/aidledger/cases/C01/case.yaml
uv run proofbench trace validate runs/<run_id>/trajectory.jsonl
uv run proofbench certificate verify runs/<run_id>/certificate.json
```

All commands must print the output path and return a meaningful exit code.

## 16. Deployment and CI

The submission deployment is local Docker. A hosted environment is not required.

CI jobs:

1. `static`: Ruff format check, Ruff lint, mypy.
2. `unit`: unit and schema tests on Python 3.12.
3. `integration`: PostgreSQL world tests with the pinned image.
4. `security`: containment and oracle-isolation tests.
5. `replay`: clean offline replay of golden artifacts.
6. `submission`: verify required docs, traces, results, and certificate links.

Cache dependencies, not run artifacts. The replay job must prove it succeeds with provider environment variables unset.

## 17. PRD traceability

| PRD requirement    | Main modules                                 | Main verification                          |
| ------------------ | -------------------------------------------- | ------------------------------------------ |
| PRD-FR-001, 002    | `workflow/intake.py`, `evaluation/runner.py` | Frozen hashes and fair-arm test            |
| PRD-FR-010 to 012  | `agents/`, `providers/`, `tools/`            | Fake-provider contract and boundary tests  |
| PRD-FR-020, 021    | `workflow/authority.py`, `domain/ruling.py`  | C04 end-to-end                             |
| PRD-FR-030 to 037  | `sandbox/`, `worlds/`                        | Passing and failing migration per world    |
| PRD-FR-040 to 042  | `decision/`, `workflow/remediation.py`       | Decision table and C01 run                 |
| PRD-FR-050 to 053  | `tracing/`                                   | Schema, hash, privacy, and narrative tests |
| PRD-FR-060, 061    | `certificate/`                               | Golden compile and offline replay          |
| PRD-FR-070 to 073  | `evaluation/`                                | Fixed manifest and metric tests            |
| PRD-NFR-001 to 006 | Make, Docker, CI, docs                       | Clean release workflow                     |

## 18. Technical completion rule

The implementation is complete when release gates R0 through R6 pass on a clean checkout, the evaluator can account for every one of the 12 cases in both arms, and a replay mismatch, oracle leak, trace failure, or required-world timeout causes a visible non-success state.
