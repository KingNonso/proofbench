"""Every registered case reaches its registered state.

This is the benchmark's own integrity check. Two failure modes it exists to
catch: a world that stopped detecting anything, and a system that learned to
reject everything. The safe controls are what make the first meaningful and the
second impossible.

The expected states are read from the evaluator-only oracle *after* each review
subprocess has closed, through the same boundary the evaluator uses.
"""

import pytest

from proofbench.domain.decision import ExternalState
from proofbench.domain.oracle import CaseClass
from proofbench.evaluation.oracle import ClosedReview, read_oracle
from proofbench.workflow.review import review_case

pytestmark = [pytest.mark.e2e, pytest.mark.integration]

ALL_CASES = [f"C{n:02d}" for n in range(1, 13)]


def run_and_score(case_id, benchmark_root, tmp_path):
    """Review a case, close it, and only then open the oracle."""
    cert, run_dir = review_case(
        benchmark_root / "cases" / case_id / "case.yaml",
        runs_root=tmp_path,
        run_id=case_id,
        remediate=False,
    )
    closed = ClosedReview(
        case_id=case_id,
        run_dir=run_dir,
        returncode=0,
        decision_path=run_dir / "decision.json",
    )
    return cert, read_oracle(benchmark_root, closed, access_log_dir=tmp_path)


@pytest.mark.parametrize("case_id", ALL_CASES)
def test_case_reaches_its_registered_state(case_id, benchmark_root, tmp_path):
    cert, oracle = run_and_score(case_id, benchmark_root, tmp_path)

    assert cert.first_screen.external_state == oracle.expected_initial_state.value, (
        f"{case_id}: worlds ran {[(r.world, r.status.value) for r in cert.world_results]}"
    )

    for invariant in oracle.expected_blocking_invariant_ids:
        assert invariant in cert.first_screen.decisive_invariant, (
            f"{case_id} blocked, but not on {invariant}"
        )


def test_the_unsafe_denominator_is_nine(benchmark_root, tmp_path):
    # PRD section 8.2. If this drifts, the escape rate is computed against a
    # different population than the one that was pre-registered.
    classes = []
    for case_id in ALL_CASES:
        (tmp_path / case_id).mkdir(parents=True, exist_ok=True)
        (tmp_path / case_id / "decision.json").write_text("{}")
        closed = ClosedReview(
            case_id=case_id,
            run_dir=tmp_path / case_id,
            returncode=0,
            decision_path=tmp_path / case_id / "decision.json",
        )
        classes.append(read_oracle(benchmark_root, closed).case_class)

    assert classes.count(CaseClass.UNSAFE) == 9
    assert classes.count(CaseClass.SAFE) == 2
    assert classes.count(CaseClass.AUTHORITY_REQUIRED) == 1


@pytest.mark.parametrize("case_id", ["C11", "C12"])
def test_a_safe_control_is_not_rejected(case_id, benchmark_root, tmp_path):
    # Without these, a system that returned BLOCKED unconditionally would score
    # a perfect escape rate.
    cert, _ = run_and_score(case_id, benchmark_root, tmp_path)
    assert cert.first_screen.external_state == ExternalState.READY_FOR_REVIEW.value
    assert cert.first_screen.confirmed_blast_radius == []


def test_the_challenging_case_exercises_every_world(benchmark_root, tmp_path):
    cert, _ = run_and_score("C12", benchmark_root, tmp_path)
    worlds = {result.world for result in cert.world_results}
    assert worlds == {"rls", "money", "rolling", "interruption", "rollback", "locks", "audit"}
    assert all(result.status.value == "passed" for result in cert.world_results)
