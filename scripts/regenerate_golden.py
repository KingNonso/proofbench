"""Regenerate the committed golden bundles for all twelve cases.

Deterministic and offline: agents run on the recorded fake provider, and only
C01 exercises the correction loop (the headline-demo bound of one attempt,
PRD-FR-042).

    uv run python scripts/regenerate_golden.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from proofbench.workflow.review import review_case  # noqa: E402

GOLDEN = REPO_ROOT / "tests" / "golden"


def main() -> int:
    for stale in GOLDEN.glob("C*"):
        shutil.rmtree(stale)
    for number in range(1, 13):
        case_id = f"C{number:02d}"
        cert, _ = review_case(
            REPO_ROOT / "benchmark" / "aidledger" / "cases" / case_id / "case.yaml",
            runs_root=GOLDEN,
            run_id=case_id,
            remediation_attempts=1 if case_id == "C01" else 0,
        )
        print(f"{case_id} {cert.first_screen.external_state}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
