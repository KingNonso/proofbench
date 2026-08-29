"""Validate the committed baseline decisions.

Makes no model call and re-runs nothing. It checks that every case has a
baseline record, that the records agree with the frozen case set, and that no
baseline decision was recorded for a case the experiment did not declare.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from proofbench.evaluation import comparison  # noqa: E402
from proofbench.evaluation.records import RunRecord  # noqa: E402
from proofbench.evaluation.runner import ALL_CASES, ARM_DIRECT_REVIEW  # noqa: E402

RESULTS = REPO_ROOT / "results"
NOT_BUILT = 3


def coverage_problems(baseline_arms: Sequence[str], records: Sequence[RunRecord]) -> list[str]:
    """Return gaps that prevent the committed baseline from satisfying PRD-FR-002."""
    problems: list[str] = []
    if ARM_DIRECT_REVIEW not in baseline_arms:
        problems.append(
            f"missing required {ARM_DIRECT_REVIEW} arm; the visible-tests arm is not "
            "the direct-review agent baseline specified by PRD-FR-002"
        )

    for arm in baseline_arms:
        seen = {record.case_id for record in records if record.arm == arm}
        missing = sorted(set(ALL_CASES) - seen)
        extra = sorted(seen - set(ALL_CASES))
        if missing:
            problems.append(f"{arm}: no record for {', '.join(missing)}")
        if extra:
            problems.append(f"{arm}: unexpected record for {', '.join(extra)}")
    return problems


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

    problems = coverage_problems(baseline_arms, records)

    print(f"protocol: {frozen['protocol']}")
    print(f"commit:   {frozen['commit']}{' (dirty)' if frozen['working_tree_dirty'] else ''}")
    print(f"baseline arms: {', '.join(baseline_arms) or 'none'}\n")

    for arm in baseline_arms:
        arm_records = [r for r in records if r.arm == arm]
        approved = sum(1 for r in arm_records if r.marked_ready)
        print(f"  {arm:<28} {len(arm_records)} decisions, {approved} would merge")

    if problems:
        print("\nEVIDENCE_NOT_BUILT: required baseline records are incomplete", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return NOT_BUILT if ARM_DIRECT_REVIEW not in baseline_arms else 1

    print("\nevery frozen case has a baseline decision")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
