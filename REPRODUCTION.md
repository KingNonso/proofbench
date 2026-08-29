# Reproduction guide

Written for someone starting from a clean environment with no Anthropic key.

The deterministic commands below have measured evidence. The complete
five-command PRD path is not yet closed: `make baseline` returns
`EVIDENCE_NOT_BUILT` until direct-review agent records are generated with a
provider key and committed for offline validation.

## What you need

| Requirement | Version used here | Why |
| --- | --- | --- |
| Docker | 27.4.0, daemon running | The sandbox starts a disposable PostgreSQL container per run |
| [`uv`](https://docs.astral.sh/uv/) | 0.9.7 | Installs the pinned Python 3.12 toolchain; the host interpreter is never used |
| `make` | GNU Make 3.81 | The five commands below |
| Disk | ~500 MB | Mostly the PostgreSQL image |

**No provider key is required to validate committed evidence.** The Anthropic SDK
is an optional extra that `make bootstrap` does not install. Producing the
currently missing PRD-FR-002 direct-review records does require the live extra
and a provider key.

```bash
uv run python -c "import importlib.util; print(importlib.util.find_spec('anthropic'))"
# None
```

PostgreSQL is pinned by OCI *index* digest
(`postgres:16@sha256:f1c3376c…6f94`), so it resolves on both arm64 and amd64. The
resolved per-platform image id is recorded in each run's certificate.

## The five commands

```bash
git clone <this repository> proofbench && cd proofbench

make bootstrap   # install pinned Python 3.12 + deps, pull the pinned database image
make test        # unit, schema, security, integration and end-to-end tests
make baseline    # currently reports EVIDENCE_NOT_BUILT: direct-review records absent
make evaluate    # recompute the metrics from the committed run records
make replay      # re-run the deterministic evidence behind all 12 golden certificates
```

### Measured runtime

From a clean clone on macOS 14 (x86_64), Docker 27.4.0, with the PostgreSQL image
already pulled:

| Command | Time | What it does |
| --- | ---: | --- |
| `make bootstrap` | 11 s | Toolchain and image. First ever run adds the image pull (~150 MB). |
| `make test` | 141 s | 239 tests, including 12 end-to-end case runs against real PostgreSQL |
| `make baseline` | <1 s | Fails honestly until committed PRD-FR-002 direct-review records exist |
| `make evaluate` | 1 s | Recomputes metrics from `results/raw-runs.jsonl`; runs nothing |
| `make replay` | 41 s | Starts a fresh database per golden bundle and re-runs its worlds |
| **Measured deterministic total** | **194 s** | Historical timing; not a claim that the open baseline gate passes |

### Cost

The offline validation commands cost zero. Producing the missing direct-review
evidence has not been costed because it has not been run.

## What you should see

`make baseline` currently ends with:

```
EVIDENCE_NOT_BUILT: required baseline records are incomplete
  missing required baseline_direct_review arm
```

`make evaluate` prints the headline result:

```
24 committed run records across 2 arm(s)
protocol: 12 cases x 2 arms x 1 repeat

  baseline_visible_tests       unsafe escape 9/9
  migration_court              unsafe escape 0/9

summary.json recomputes exactly from raw-runs.jsonl
```

`make replay` ends with:

```
all 12 golden certificate(s) reproduced
```

Each bundle prints its own verification first — bundle root, artifact digests,
trace chain, declared inputs, then the re-executed worlds and the decision.

## Looking at one result yourself

```bash
# Review a candidate and read the certificate
uv run proofbench review benchmark/aidledger/cases/C01/case.yaml
open runs/<run_id>/certificate.html        # macOS; xdg-open on Linux

# The committed golden bundle for the same case
open tests/golden/C01/certificate.html
cat  tests/golden/C01/trajectory.md
```

`review` exits non-zero for a blocked candidate, so it composes with CI.

The human authority path, both determinations:

```bash
uv run proofbench review benchmark/aidledger/cases/C04/case.yaml
# -> DOMAIN_RULING_REQUIRED, and writes runs/<id>/ruling-packet.md

uv run proofbench review benchmark/aidledger/cases/C04/case.yaml \
  --ruling benchmark/aidledger/cases/C04/rulings/currency-uniformly-usd.yaml
# -> READY_FOR_REVIEW

uv run proofbench review benchmark/aidledger/cases/C04/case.yaml \
  --ruling benchmark/aidledger/cases/C04/rulings/currency-per-organisation.yaml
# -> BLOCKED on INV-MONEY-002
```

## Regenerating the evidence (optional, and not the judge path)

These produce evidence rather than verifying it. The first needs no key; the
second does.

```bash
uv run python scripts/run_experiment.py        # re-runs both deterministic arms
uv run python scripts/measure_sandbox.py       # re-measures the timings above

uv sync --extra live                           # installs the Anthropic SDK
make evaluate-live                             # adds the direct-review agent baseline
```

`make evaluate-live` is the only command in this repository that calls a model.
It needs `ANTHROPIC_API_KEY`, or a profile from `ant auth login`. It has **not**
been run, so no result in this repository depends on it — see `results/comparison.md`.

## If something fails

| Symptom | Cause | Fix |
| --- | --- | --- |
| `docker is not available on PATH` | Docker not installed or daemon stopped | Start Docker Desktop, or `sudo systemctl start docker` |
| `database did not become ready` | Container could not start; the error carries the container logs | Check `docker ps -a`; usually memory pressure |
| `make test` fails only on integration tests | Docker daemon not running | The unit suite alone: `uv run pytest -m "not integration and not security and not e2e"` |
| A leaked container after an interrupted run | The run was killed between start and cleanup | `docker ps -aq --filter label=proofbench.run_id \| xargs docker rm -f` |

Every run labels its container and network with `proofbench.run_id`, so an orphan
is always findable.

## Verifying the artifacts by hand

```bash
uv run proofbench certificate verify tests/golden/C01/certificate.json
uv run proofbench trace validate tests/golden/C01/trajectory.jsonl
shasum -a 256 hackathon-brief.pdf   # be811a1d09ebedef2fc853544132b287924fd0f76d04301ea554b4c7e2d88fc4
```

Tampering is detected rather than tolerated. Change a byte of a committed
candidate and `make replay` fails, naming the file:

```bash
echo "-- tampered" >> benchmark/aidledger/cases/C01/candidate.sql
make replay          # [FAIL] 7 declared inputs are unchanged — changed: cases/C01/candidate.sql
git checkout benchmark/aidledger/cases/C01/candidate.sql
```
