#!/usr/bin/env bash
# Re-run the deterministic evidence behind every committed golden certificate.
#
# This is the judge's reproduction command. It must work with no provider
# variable set, and it must fail loudly rather than pass vacuously when there is
# nothing committed to verify.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
shopt -s nullglob
bundles=("$root"/tests/golden/*/certificate.json)

if [ ${#bundles[@]} -eq 0 ]; then
  cat >&2 <<'MSG'
EVIDENCE_NOT_BUILT: make replay

  No golden certificate is committed yet.
  Expected: tests/golden/*/certificate.json

  See README.md "Status". This is a truthful failure, not a broken installation.
MSG
  exit 3
fi

# PRD-FR-030..037 acceptance: the same golden inputs must produce the same
# semantic results on THREE replay runs. One reproduction is a lucky draw;
# three is stability. REPLAY_RUNS=1 exists for a quick local smoke, never for
# the gate.
runs="${REPLAY_RUNS:-3}"

failed=0
for bundle in "${bundles[@]}"; do
  case_dir="$(basename "$(dirname "$bundle")")"
  echo "--- replaying ${case_dir} (${runs}x) ---"
  for attempt in $(seq 1 "$runs"); do
    if ! uv run proofbench replay "$bundle"; then
      echo "MISMATCH on run ${attempt} of ${runs} for ${case_dir}" >&2
      failed=1
    fi
  done
  echo
done

if [ "$failed" -ne 0 ]; then
  echo "REPLAY MISMATCH: at least one golden certificate did not reproduce on every run" >&2
  exit 1
fi

echo "all ${#bundles[@]} golden certificate(s) reproduced on ${runs} consecutive run(s)"
