"""Run the frozen paired experiment and write its evidence.

Evidence-production, not part of the clean judge path. `make evaluate` recomputes
the metrics from what this wrote; it does not re-run anything.

    uv run python scripts/run_experiment.py                       # deterministic arms
    uv run python scripts/run_experiment.py \
        --with-agent-baseline --provider claude_cli               # live, needs a login

The experiment record is written *before* the first run, so the protocol cannot
be chosen after seeing the results, and it carries the provider, resolved CLI
version, budgets, seeds, prompt hashes, and image pin so the record says what
actually ran. A live experiment refuses to start from a dirty working tree:
"which code produced this" must have one answer.
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

from proofbench.agents.contract_analyst import PROMPT_PATH as CONTRACT_PROMPT  # noqa: E402
from proofbench.agents.remediation_engineer import PROMPT_PATH as REMEDIATION_PROMPT  # noqa: E402
from proofbench.agents.test_designer import PROMPT_PATH as TEST_DESIGNER_PROMPT  # noqa: E402
from proofbench.certificate.replay import replay as replay_bundle  # noqa: E402
from proofbench.config import POSTGRES_IMAGE  # noqa: E402
from proofbench.evaluation import comparison  # noqa: E402
from proofbench.evaluation.baseline import REVIEWER_PROMPT  # noqa: E402
from proofbench.evaluation.runner import (  # noqa: E402
    ALL_CASES,
    ARM_DIRECT_REVIEW,
    ARM_FINAL,
    ARM_SELF_REVIEW,
    ARM_VISIBLE_TESTS,
    run_arm,
)
from proofbench.providers.base import ModelProvider  # noqa: E402
from proofbench.providers.registry import create_provider, provider_kinds  # noqa: E402
from proofbench.tracing.hashes import hash_file  # noqa: E402

BENCHMARK = REPO_ROOT / "benchmark" / "aidledger"
RESULTS = REPO_ROOT / "results"
GOLDEN = REPO_ROOT / "tests" / "golden"

# PRD-FR-070 fallback: every case once, these four three times.
REPEAT_CASES = ["C01", "C04", "C08", "C12"]
REPEATS = 3

# The condition-level model-token ceiling, identical for every arm of one
# experiment (PRD-FR-002 "same budget"): the final arm spends it across its
# agents, the direct reviewer gets all of it. Enforced per case-run by the
# budget ledger, which invalidates a run that crosses it. Sized for the
# measured CLI harness overhead (~25-29k input tokens per codex exec call,
# observed live): three agent calls plus one repair round must fit.
DEFAULT_MAX_TOTAL_TOKENS = 250_000

DETERMINISTIC_NOTE = (
    "Both arms here are deterministic and make no network call. The baseline is "
    "`visible-tests`: run the checks that already exist in CI and merge if they pass, "
    "which is the process this product is meant to improve on. The direct-review agent "
    "baseline specified by PRD-FR-002 is implemented but is NOT included in this run: "
    "it needs a live provider (an authenticated subscription CLI or an API profile), "
    "and authoring its answers would make the comparison meaningless. Until it runs, "
    "no claim may be made about how ProofBench compares to a reviewing agent."
)


def agent_note(provider: ModelProvider, role: str) -> str:
    model = getattr(provider, "model", "unknown")
    return (
        "Three arms: the visible-tests baseline, the direct-review agent baseline "
        "(PRD-FR-002, same candidate, schema, roles, policy, tests, model family and "
        "budget as the final workflow), and Migration Court. Both live arms are served "
        f"by the same provider: {provider.name} ({model}). This is the {role} "
        "experiment; metrics from different providers are never pooled."
    )


def assert_manifest_frozen() -> None:
    """Refuse to run against an unfrozen or drifted manifest.

    Sequence gate S7: no experiment result changes the frozen case manifest.
    Enforced here rather than trusted, because the one thing an experiment
    script must not be able to do is quietly measure a different benchmark than
    the one that was registered.
    """
    import hashlib

    import yaml

    manifest = yaml.safe_load((BENCHMARK / "manifest.yaml").read_text(encoding="utf-8"))
    problems = []
    for case in manifest["cases"]:
        if not case.get("frozen"):
            problems.append(f"{case['case_id']} is not frozen")
            continue
        actual = hashlib.sha256((BENCHMARK / case["path"]).read_bytes()).hexdigest()
        if case.get("sha256") != actual:
            problems.append(f"{case['case_id']} drifted from its frozen hash")
    if problems:
        raise SystemExit(
            "refusing to run: the case manifest is not frozen, or a case changed "
            "after freezing:\n  " + "\n  ".join(problems)
        )


REPLAY_STABILITY_RUNS = 3


def replay_golden_bundles() -> tuple[int, int]:
    """Replay every committed golden certificate and count the reproductions.

    PRD-FR-072 requires the clean replay rate in the report. Measured here, at
    experiment time, rather than copied from the last time someone ran replay —
    and measured to the PRD-FR-030..037 acceptance: a bundle counts as
    reproduced only when three consecutive replays agree.
    """
    bundles = sorted(GOLDEN.glob("C*/certificate.json"))
    passed = 0
    for bundle in bundles:
        reports = [
            replay_bundle(bundle, benchmark_root=BENCHMARK) for _ in range(REPLAY_STABILITY_RUNS)
        ]
        ok = all(report.ok for report in reports)
        status = "reproduced 3x" if ok else "MISMATCH"
        print(f"  replay {reports[0].case_id}: {status}", flush=True)
        if ok:
            passed += 1
    return passed, len(bundles)


def git_state() -> tuple[str, bool]:
    """The commit that produced this evidence, and whether the tree drifted."""
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
        return "unknown", True
    return commit, dirty


def case_seeds() -> dict[str, int]:
    """The per-case replay seeds, read from the frozen case files.

    These seed the deterministic harness. No live provider interface accepts a
    sampling seed, and the record says so explicitly rather than implying that
    the seed reached the model.
    """
    import yaml

    return {
        case_id: int(
            yaml.safe_load(
                (BENCHMARK / "cases" / case_id / "case.yaml").read_text(encoding="utf-8")
            )["seed"]
        )
        for case_id in ALL_CASES
    }


def provider_record(provider: ModelProvider, kind: str) -> dict[str, object]:
    """Everything the manifest must say about who served the model calls."""
    record: dict[str, object] = {
        "kind": kind,
        "name": provider.name,
        "mode": provider.mode,
        "requested_model": getattr(provider, "model", ""),
        "auth_mode": "subscription_cli" if kind.endswith("_cli") else "api_key_or_profile",
        "cost_basis": getattr(provider, "cost_basis", "unavailable"),
        "sampling_seed": "unsupported-by-provider-interface",
    }
    preflight = getattr(provider, "preflight", None)
    if callable(preflight):
        # Fails loudly (EVIDENCE_INCOMPLETE) if the executable is missing,
        # before a single case runs.
        record.update(preflight())
    argv_template = getattr(provider, "argv_template", None)
    if callable(argv_template):
        record["argv_template"] = argv_template()
    return record


def freeze_experiment(
    protocol: str,
    arms: list[str],
    note: str,
    *,
    role: str,
    provider_info: dict[str, object] | None,
    max_total_tokens: int,
    out_dir: Path = RESULTS,
) -> dict[str, object]:
    """Record what is about to be run, before any of it runs.

    The record carries its own hash (computed over everything else in it), and
    ``summary.json`` must quote that hash before any metric may be spoken
    (PRD §16).
    """
    commit, dirty = git_state()

    record: dict[str, object] = {
        "schema_version": "1.1",
        "started_at": datetime.now(UTC).isoformat(),
        "protocol": protocol,
        "role": role,
        "arms": arms,
        "cases": ALL_CASES,
        "note": note,
        "commit": commit,
        "working_tree_dirty": dirty,
        "host": {"platform": platform.platform(), "python": platform.python_version()},
        "provider": provider_info,
        "budget": {
            "max_total_tokens_per_case_run": max_total_tokens,
            "policy": "identical ceiling for every arm; over-budget runs are invalidated",
        },
        "seeds": case_seeds(),
        "postgres_image": POSTGRES_IMAGE,
        "prompt_hashes": {
            "contract_analyst_v1": hash_file(CONTRACT_PROMPT),
            "test_designer_v1": hash_file(TEST_DESIGNER_PROMPT),
            "remediation_engineer_v1": hash_file(REMEDIATION_PROMPT),
            "direct_reviewer_v1": hash_file(REVIEWER_PROMPT),
        },
        "case_hashes": {
            case_id: hash_file(BENCHMARK / "cases" / case_id / "case.yaml") for case_id in ALL_CASES
        },
        "policy_hash": hash_file(BENCHMARK / "policies" / "base-policy.yaml"),
    }
    record["experiment_hash"] = comparison.experiment_hash(record)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "experiment.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return record


def run_e1(
    args: argparse.Namespace,
    provider: ModelProvider,
    provider_info: dict[str, object] | None,
) -> int:
    """E1, the equal-budget self-review changelog experiment (PRD-FR-073).

    One arm, twelve cases, one pass, the same condition ceiling as the paired
    protocol. Its evidence lives in its own directory so it can never be
    mistaken for — or pooled with — the paired comparison.
    """
    e1_dir = RESULTS / "e1-self-review"
    model = getattr(provider, "model", "unknown")
    protocol = "E1 changelog experiment: 12 cases x 1 arm (baseline_self_review) x 1 repeat"
    note = (
        "E1 equal-budget self-review: the PRD-FR-002 direct reviewer, given its "
        "condition budget back to re-examine its own decision with no new evidence "
        f"and no worlds. Provider: {provider.name} ({model}). A changelog "
        "experiment — never part of the paired protocol, never pooled with it."
    )

    assert_manifest_frozen()
    experiment = freeze_experiment(
        protocol,
        [ARM_SELF_REVIEW],
        note,
        role="changelog-e1",
        provider_info=provider_info,
        max_total_tokens=args.max_total_tokens,
        out_dir=e1_dir,
    )

    print(f"--- {ARM_SELF_REVIEW} ---", flush=True)
    records = run_arm(
        ARM_SELF_REVIEW,
        benchmark_root=BENCHMARK,
        runs_root=args.runs_root / "e1",
        case_ids=ALL_CASES,
        repeat=1,
        provider=provider,
        max_total_tokens=args.max_total_tokens,
    )
    for record in records:
        flag = "ready" if record.marked_ready else record.outcome
        print(f"  r1 {record.case_id} {record.case_class:<18} {flag}", flush=True)

    comparison.write_raw_runs(records, e1_dir / "raw-runs.jsonl")
    comparison.write_per_case(records, e1_dir / "per-case.csv")
    summary = comparison.summarise(
        records,
        protocol=protocol,
        note=note,
        experiment_hash_value=str(experiment["experiment_hash"]),
    )
    comparison.write_summary(summary, e1_dir / "summary.json")

    metric = summary["primary_metric"]["by_arm"][ARM_SELF_REVIEW]  # type: ignore[index]
    print(
        f"\nE1 unsafe escape: {metric['numerator']}/{metric['denominator']}"
        f"\nexperiment hash: {experiment['experiment_hash']}"
        f"\nwrote {e1_dir.relative_to(REPO_ROOT)}/"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--with-agent-baseline", action="store_true")
    parser.add_argument(
        "--e1",
        action="store_true",
        help="run the E1 equal-budget self-review changelog experiment instead "
        "of the paired protocol (12 cases once, one arm, same ceiling)",
    )
    parser.add_argument(
        "--provider",
        choices=provider_kinds(),
        help="live provider for BOTH live arms; required with --with-agent-baseline",
    )
    parser.add_argument("--model", help="override the provider's default model")
    parser.add_argument(
        "--role",
        choices=("primary", "replication"),
        default="primary",
        help="primary closes the release gates; a replication is labelled as such",
    )
    parser.add_argument("--max-total-tokens", type=int, default=DEFAULT_MAX_TOTAL_TOKENS)
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="let a live experiment run from a dirty tree (recorded either way)",
    )
    parser.add_argument("--runs-root", type=Path, default=REPO_ROOT / "runs" / "experiment")
    args = parser.parse_args()

    if args.e1 and args.with_agent_baseline:
        parser.error("--e1 is a separate changelog experiment; run it on its own")

    arms = [ARM_VISIBLE_TESTS, ARM_FINAL]
    note = DETERMINISTIC_NOTE
    provider: ModelProvider | None = None
    provider_info: dict[str, object] | None = None
    if args.with_agent_baseline or args.e1:
        if not args.provider:
            parser.error("a live experiment requires --provider")
        _, dirty = git_state()
        if dirty and not args.allow_dirty:
            print(
                "refusing to run a live experiment from a dirty working tree: "
                "'which code produced this' must have one answer. Commit first, "
                "or pass --allow-dirty to record the drift knowingly.",
                file=sys.stderr,
            )
            return 2
        provider = create_provider(args.provider, model=args.model)
        provider_info = provider_record(provider, args.provider)
        print(f"provider preflight: {provider_info.get('version', 'n/a')}", flush=True)

    if args.e1 and provider is not None:
        return run_e1(args, provider, provider_info)

    if args.with_agent_baseline and provider is not None:
        arms.insert(1, ARM_DIRECT_REVIEW)
        note = agent_note(provider, args.role)

    assert_manifest_frozen()

    protocol = (
        f"PRD-FR-070 fallback: 12 cases x {len(arms)} arms x 1 repeat, "
        f"plus {', '.join(REPEAT_CASES)} x{REPEATS}"
    )
    experiment = freeze_experiment(
        protocol,
        arms,
        note,
        role=args.role,
        provider_info=provider_info,
        max_total_tokens=args.max_total_tokens,
    )

    records = []
    for arm in arms:
        print(f"--- {arm} ---", flush=True)
        for repeat in range(1, REPEATS + 1):
            cases = ALL_CASES if repeat == 1 else REPEAT_CASES
            arm_records = run_arm(
                arm,
                benchmark_root=BENCHMARK,
                runs_root=args.runs_root,
                case_ids=cases,
                repeat=repeat,
                provider=provider,
                max_total_tokens=args.max_total_tokens,
            )
            for record in arm_records:
                flag = "ready" if record.marked_ready else record.outcome
                print(f"  r{repeat} {record.case_id} {record.case_class:<18} {flag}", flush=True)
            records.extend(arm_records)

    print("--- replaying golden certificates ---", flush=True)
    clean_replay = replay_golden_bundles()

    comparison.write_raw_runs(records, RESULTS / "raw-runs.jsonl")
    comparison.write_per_case(records, RESULTS / "per-case.csv")
    summary = comparison.summarise(
        records,
        protocol=protocol,
        note=note,
        clean_replay=clean_replay,
        experiment_hash_value=str(experiment["experiment_hash"]),
    )
    comparison.write_summary(summary, RESULTS / "summary.json")
    comparison.write_comparison(records, summary, RESULTS / "comparison.md")

    print("\n=== primary metric: unsafe migration escape rate ===")
    for arm, values in sorted(summary["primary_metric"]["by_arm"].items()):
        print(f"  {arm:<28} {values['numerator']}/{values['denominator']}")
    print(f"clean replay: {clean_replay[0]}/{clean_replay[1]}")
    stability = summary["repeat_stability"]
    for arm in sorted(stability):
        print(
            f"repeat stability {arm}: "
            f"{'identical' if stability[arm]['all_identical'] else 'DISAGREED'}"
        )
    print(f"experiment hash: {experiment['experiment_hash']}")
    print(f"\nwrote {RESULTS.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
