#!/usr/bin/env bash
# Deterministic driver for the five-minute video (gate R6).
#
# Runs the exact commands submission/video-script.md narrates, in shot order,
# pausing for ENTER before each so the recording can be cut per shot. It drives
# the deterministic replay path only — never a live provider run
# (implementation-sequence.md §14: "Record the deterministic replay, not a
# fragile live provider run").
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"

if [ -n "${ANTHROPIC_API_KEY:-}" ] || [ -n "${OPENAI_API_KEY:-}" ]; then
  echo "unset provider variables before recording; the judge path needs none" >&2
  exit 2
fi

shot() {
  printf '\n\n=== %s ===\n' "$1"
  read -rp '[ENTER to run] '
}

show() {
  printf '\n    open in editor/browser: %s\n' "$1"
  read -rp '[ENTER when framed] '
}

shot "0:00 Problem — candidate beside its passing visible test"
show "benchmark/aidledger/cases/C01/candidate.sql"
show "benchmark/aidledger/cases/C01/visible_tests/001_schema_shape.sql"

shot "0:30 Baseline — read the counts off the screen"
uv run python scripts/evaluate.py

shot "1:00 Architecture — the three agents' stages"
show "tests/golden/C01/trajectory.md"

shot "1:35 One real execution — timeline, then the certificate"
show "tests/golden/C01/trajectory.md"
show "tests/golden/C01/certificate.html"

shot "2:35 The human boundary — the ruling packet"
show "tests/golden/C04/ruling-packet.md"

shot "3:00 The finished artifact — scroll the certificate once"
show "tests/golden/C01/certificate.html"

shot "3:30 Measured improvement — the comparison report"
show "results/comparison.md"

shot "4:05 Reproducibility — three consecutive replays per bundle"
make replay

shot "4:30 Changelog — the removed experiment"
show "results/improvement-changelog.md"

shot "4:50 Hot take — the three-row table"
show "README.md"

printf '\n\ndone — check the cut against tests/e2e/test_claim_lock.py before publishing\n'
