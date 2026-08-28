# Provenance

Required by hackathon brief ground rule 02: "Make it clear what existed before the
competition and what you added."

## Statement

**Nothing in this repository predates the competition.** There is no pre-existing source
code, test suite, benchmark fixture, Git history, or CI pipeline being reused.

The competition kickoff was 16:00 WAT on 2026-08-28. Every file in this repository was
created after that time.

## Classification

| Artifact | Created | Classification |
| --- | --- | --- |
| `proofbench-prd.md` | 2026-08-28 19:54 WAT | Hackathon-created planning work |
| `implementation-plan.md` | 2026-08-28 19:54 WAT | Hackathon-created planning work |
| `implementation-sequence.md` | 2026-08-28 19:55 WAT | Hackathon-created planning work |
| `5-min-presentation.md` | 2026-08-28 19:56 WAT | Hackathon-created planning work |
| `hackathon-brief.pdf` | Supplied by organisers | Competition material, not authored here |
| `claude-plan-engineering-review.md` | 2026-08-28 20:21 WAT | Hackathon-created engineering review |
| `docs/`, `src/`, `tests/`, `benchmark/`, configuration, CI | After 2026-08-28 20:30 WAT | Hackathon-created implementation |

The four planning documents were written after kickoff and are **not** pre-existing work.
They are design work produced during the competition.

## Commit boundary

Two initial commits make the boundary auditable:

1. **Implementation baseline** — planning documents, the brief, and Phase 0 evidence.
   This proves the design existed *before implementation*. It does not and cannot prove
   anything existed before the competition.
2. **Scaffold** — project configuration, engineering standards, and the typed intake slice.

Any reviewer can verify this with `git log --reverse --stat`.

## Third-party components

Reused under their own licenses, none authored here: Python, `uv`, Pydantic, Typer, PyYAML,
pytest, Ruff, mypy, Docker, and the official PostgreSQL 16 image. A full dependency and
license inventory is maintained in `CHANGELOG.md`.

## Assistance disclosure

This project was built with AI coding assistance. Engineering standards constraining that
assistance are in `AGENTS.md`. The three *product* agents that ProofBench itself runs are a
separate matter, documented in `AGENT_DISCLOSURE.md`.
