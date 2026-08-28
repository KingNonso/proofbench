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

failed=0
for bundle in "${bundles[@]}"; do
  case_dir="$(basename "$(dirname "$bundle")")"
  echo "--- replaying ${case_dir} ---"
  if ! uv run proofbench replay "$bundle"; then
    failed=1
  fi
  echo
done

if [ "$failed" -ne 0 ]; then
  echo "REPLAY MISMATCH: at least one golden certificate did not reproduce" >&2
  exit 1
fi

echo "all ${#bundles[@]} golden certificate(s) reproduced"
