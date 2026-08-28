# CLAUDE.md

Engineering standards for this repository live in **[AGENTS.md](AGENTS.md)**. Read that file
first; it is the single source of truth and applies to every agent and human working here.

@AGENTS.md

## Claude Code specifics

- The product contract is `proofbench-prd.md`. The build order is `implementation-sequence.md`,
  as amended by `claude-plan-engineering-review.md`. Phase 0 evidence is in `docs/`.
- Run commands through `uv run`, never a bare `python` or `pip`.
- Integration and security tests need a running Docker daemon. If it is not available, say so
  and skip with a reason. Never silently drop them from a run and report success.
- Before saying a slice is complete, run `make check` and paste the real result. If something
  fails, report the failure — a truthful red is worth more than a green claim here, because
  every claim in this project has to survive a claim-lock table.
