"""Validate the committed baseline decisions.

Makes no model call and re-runs nothing. It checks that every case has a
baseline record, that the records agree with the frozen case set, and that no
baseline decision was recorded for a case the experiment did not declare.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from proofbench.evaluation import comparison  # noqa: E402
from proofbench.evaluation.runner import ALL_CASES  # noqa: E402

RESULTS = REPO_ROOT / "results"
NOT_BUILT = 3


def main() -> int:
    raw = RESULTS / "raw-runs.jsonl"
    experiment = RESULTS / "experiment.json"

    if not raw.is_file() or not experiment.is_file():
        print(
            "EVIDENCE_NOT_BUILT: make baseline\n\n"
            "  No committed baseline records to validate.\n"
            "  Expected: results/raw-runs.jsonl and results/experiment.json\n\n"
            "  Produce them with: uv run python scripts/run_experiment.py\n",
            file=sys.stderr,
        )
        return NOT_BUILT

    records = comparison.read_raw_runs(raw)
    frozen = json.loads(experiment.read_text(encoding="utf-8"))
    baseline_arms = [arm for arm in frozen["arms"] if arm.startswith("baseline")]

    problems: list[str] = []
    for arm in baseline_arms:
        seen = {record.case_id for record in records if record.arm == arm}
        missing = sorted(set(ALL_CASES) - seen)
        extra = sorted(seen - set(ALL_CASES))
        if missing:
            problems.append(f"{arm}: no record for {', '.join(missing)}")
        if extra:
            problems.append(f"{arm}: unexpected record for {', '.join(extra)}")

    print(f"protocol: {frozen['protocol']}")
    print(f"commit:   {frozen['commit']}{' (dirty)' if frozen['working_tree_dirty'] else ''}")
    print(f"baseline arms: {', '.join(baseline_arms) or 'none'}\n")

    for arm in baseline_arms:
        arm_records = [r for r in records if r.arm == arm]
        approved = sum(1 for r in arm_records if r.marked_ready)
        print(f"  {arm:<28} {len(arm_records)} decisions, {approved} would merge")

    if problems:
        print("\nBASELINE RECORDS ARE INCOMPLETE", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print("\nevery frozen case has a baseline decision")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
