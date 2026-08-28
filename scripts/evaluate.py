"""Recompute the metrics from committed run records and verify the summary.

Makes no model call and re-runs nothing. Its job is to prove that
`results/summary.json` follows from `results/raw-runs.jsonl` — so a number in the
submission cannot drift from the runs it came from.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from proofbench.evaluation import comparison  # noqa: E402

RESULTS = REPO_ROOT / "results"
NOT_BUILT = 3


def main() -> int:
    raw = RESULTS / "raw-runs.jsonl"
    summary_path = RESULTS / "summary.json"

    if not raw.is_file() or not summary_path.is_file():
        print(
            "EVIDENCE_NOT_BUILT: make evaluate\n\n"
            "  No committed experiment evidence to recompute.\n"
            "  Expected: results/raw-runs.jsonl and results/summary.json\n\n"
            "  Produce it with: uv run python scripts/run_experiment.py\n",
            file=sys.stderr,
        )
        return NOT_BUILT

    records = comparison.read_raw_runs(raw)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    problems = comparison.verify(records, summary)

    print(f"{len(records)} committed run records across {len({r.arm for r in records})} arm(s)")
    print(f"protocol: {summary['protocol']}\n")
    for arm, values in sorted(summary["primary_metric"]["by_arm"].items()):
        print(f"  {arm:<28} unsafe escape {values['numerator']}/{values['denominator']}")

    replay = summary.get("clean_replay")
    if replay:
        print(f"\n  clean replay                 {replay['numerator']}/{replay['denominator']}")
    stability = summary.get("repeat_stability", {})
    for arm in sorted(stability):
        entry = stability[arm]
        if entry.get("repeated_cases"):
            verdict = "identical" if entry["all_identical"] else "DISAGREED"
            print(
                f"  repeat stability {arm:<11} {verdict} "
                f"({', '.join(entry['repeated_cases'])} x{max(entry['repeats_per_case'].values())})"
            )

    if problems:
        print("\nSUMMARY DOES NOT FOLLOW FROM THE RAW RUNS", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    print("\nsummary.json recomputes exactly from raw-runs.jsonl")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
