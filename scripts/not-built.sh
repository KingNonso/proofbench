#!/usr/bin/env bash
# Fail honestly for a release target whose evidence does not exist yet.
#
# A judge-facing target must never pass as a no-op: a green command that
# verified nothing is worse than a red one that says why.
set -euo pipefail

target="${1:?target name required}"
expected="${2:?expected evidence required}"

cat >&2 <<MSG
EVIDENCE_NOT_BUILT: make ${target}

  This target verifies committed evidence that does not exist yet.
  Expected: ${expected}

  See README.md "Status" for what is built. This is a truthful failure,
  not a broken installation.
MSG
exit 3
