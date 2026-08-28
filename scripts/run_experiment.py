"""Run the frozen paired experiment and write its evidence.

Evidence-production, not part of the clean judge path. `make evaluate` recomputes
the metrics from what this wrote; it does not re-run anything.

    uv run python scripts/run_experiment.py                 # deterministic arms
    uv run python scripts/run_experiment.py --with-agent-baseline   # needs a key

The experiment record is written *before* the first run, so the protocol cannot
be chosen after seeing the results.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from proofbench.evaluation import comparison  # noqa: E402
from proofbench.evaluation.runner import (  # noqa: E402
    ALL_CASES,
    ARM_DIRECT_REVIEW,
    ARM_FINAL,
    ARM_VISIBLE_TESTS,
    run_arm,
)
from proofbench.tracing.hashes import hash_file  # noqa: E402

BENCHMARK = REPO_ROOT / "benchmark" / "aidledger"
RESULTS = REPO_ROOT / "results"

DETERMINISTIC_NOTE = (
    "Both arms here are deterministic and make no network call. The baseline is "
    "`visible-tests`: run the checks that already exist in CI and merge if they pass, "
    "which is the process this product is meant to improve on. The direct-review agent "
    "baseline specified by PRD-FR-002 is implemented but is NOT included in this run: "
    "it needs a provider key, and authoring its answers would make the comparison "
    "meaningless. Until it runs, no claim may be made about how ProofBench compares to "
    "a reviewing agent."
)
AGENT_NOTE = (
    "Three arms: the visible-tests baseline, the direct-review agent baseline "
    "(PRD-FR-002, same candidate, schema, roles, policy, tests, model family and "
    "budget as the final workflow), and Migration Court."
)


def freeze_experiment(protocol: str, arms: list[str], note: str) -> dict[str, object]:
    """Record what is about to be run, before any of it runs."""
    try:
        commit = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
            timeout=10,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(  # noqa: S603
                ["git", "status", "--porcelain"],  # noqa: S607
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
                check=False,
                timeout=10,
            ).stdout.strip()
        )
    except (OSError, subprocess.SubprocessError):
        commit, dirty = "unknown", True

    record = {
        "schema_version": "1.0",
        "started_at": datetime.now(UTC).isoformat(),
        "protocol": protocol,
        "arms": arms,
        "cases": ALL_CASES,
        "note": note,
        "commit": commit,
        "working_tree_dirty": dirty,
        "host": {"platform": platform.platform(), "python": platform.python_version()},
        "case_hashes": {
            case_id: hash_file(BENCHMARK / "cases" / case_id / "case.yaml") for case_id in ALL_CASES
        },
        "policy_hash": hash_file(BENCHMARK / "policies" / "base-policy.yaml"),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "experiment.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-agent-baseline", action="store_true")
    parser.add_argument("--runs-root", type=Path, default=REPO_ROOT / "runs" / "experiment")
    args = parser.parse_args()

    arms = [ARM_VISIBLE_TESTS, ARM_FINAL]
    note = DETERMINISTIC_NOTE
    provider = None
    if args.with_agent_baseline:
        from proofbench.providers.live import LiveProvider  # noqa: PLC0415

        provider = LiveProvider()
        arms.insert(1, ARM_DIRECT_REVIEW)
        note = AGENT_NOTE

    protocol = f"12 cases x {len(arms)} arms x 1 repeat"
    freeze_experiment(protocol, arms, note)

    records = []
    for arm in arms:
        print(f"--- {arm} ---", flush=True)
        arm_records = run_arm(
            arm,
            benchmark_root=BENCHMARK,
            runs_root=args.runs_root,
            provider=provider,
        )
        for record in arm_records:
            flag = "ready" if record.marked_ready else record.outcome
            print(f"  {record.case_id} {record.case_class:<18} {flag}", flush=True)
        records.extend(arm_records)

    comparison.write_raw_runs(records, RESULTS / "raw-runs.jsonl")
    comparison.write_per_case(records, RESULTS / "per-case.csv")
    summary = comparison.summarise(records, protocol=protocol, note=note)
    comparison.write_summary(summary, RESULTS / "summary.json")
    comparison.write_comparison(records, summary, RESULTS / "comparison.md")

    print("\n=== primary metric: unsafe migration escape rate ===")
    for arm, values in sorted(summary["primary_metric"]["by_arm"].items()):
        print(f"  {arm:<28} {values['numerator']}/{values['denominator']}")
    print(f"\nwrote {RESULTS.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
