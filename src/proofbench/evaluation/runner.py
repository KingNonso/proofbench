"""Run the paired experiment.

Both arms see identical frozen inputs: the same candidate, the same schema and
roles, the same visible tests, the same policy (PRD-FR-070). The only thing that
differs is what each arm does with them.

Scoring happens strictly after a run closes. The oracle is opened through
``evaluation.oracle``, which requires a ``ClosedReview``, so a run cannot be
influenced by the answer it is about to be graded against.
"""

from __future__ import annotations

import json
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from proofbench.domain.decision import ExternalState
from proofbench.errors import EvidenceIncompleteError
from proofbench.evaluation.baseline import review_by_agent, review_by_visible_tests
from proofbench.evaluation.oracle import ClosedReview, read_oracle
from proofbench.evaluation.records import (
    MARKED_READY_BASELINE,
    MARKED_READY_FINAL,
    RunRecord,
)
from proofbench.intake.loader import load_case
from proofbench.providers.base import ModelProvider
from proofbench.providers.budget import BudgetLedger, MeteredProvider
from proofbench.tracing.hashes import canonical_json
from proofbench.workflow.review import review_case

ALL_CASES = [f"C{n:02d}" for n in range(1, 13)]

ARM_FINAL = "migration_court"
ARM_VISIBLE_TESTS = "baseline_visible_tests"
ARM_DIRECT_REVIEW = "baseline_direct_review"


def run_arm(
    arm: str,
    *,
    benchmark_root: Path,
    runs_root: Path,
    case_ids: Sequence[str] = ALL_CASES,
    repeat: int = 1,
    provider: ModelProvider | None = None,
    max_total_tokens: int | None = None,
) -> list[RunRecord]:
    """Run one arm over the given cases and score each run after it closes.

    The same provider reaches both arms — a live baseline compared against a
    fixture-replay final arm is not a comparison, it is a category error, and
    it is exactly what this function used to do. ``max_total_tokens`` is the
    condition ceiling, identical for every arm of one experiment (PRD-FR-002).
    """
    records: list[RunRecord] = []

    for case_id in case_ids:
        case_path = benchmark_root / "cases" / case_id / "case.yaml"
        run_dir = runs_root / arm / f"{case_id}-r{repeat}"
        clock = time.monotonic()

        # A fresh ledger per run: the ceiling bounds one case-run, so an
        # expensive case cannot starve the cases after it.
        ledger: BudgetLedger | None = None
        run_provider: ModelProvider | None = provider
        if provider is not None:
            ledger = BudgetLedger(max_total_tokens=max_total_tokens)
            run_provider = MeteredProvider(provider, ledger)

        try:
            if arm == ARM_FINAL:
                record = _run_final(arm, case_id, repeat, case_path, run_dir, clock, run_provider)
            else:
                record = _run_baseline(
                    arm, case_id, repeat, case_path, run_dir, clock, run_provider
                )
        except EvidenceIncompleteError as exc:
            record = RunRecord(
                arm=arm,
                case_id=case_id,
                repeat=repeat,
                outcome="EVIDENCE_INCOMPLETE",
                marked_ready=False,
                evidence_incomplete=True,
                asked_for_authority=False,
                duration_ms=int((time.monotonic() - clock) * 1000),
                note=exc.message,
            )
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "decision.json").write_bytes(
                canonical_json({"external_state": "EVIDENCE_INCOMPLETE", "reason": exc.message})
            )

        record = _account(record, provider, ledger, max_total_tokens)

        # Only now, with the decision written and immutable, is the oracle opened.
        oracle = read_oracle(
            benchmark_root,
            ClosedReview(
                case_id=case_id,
                run_dir=run_dir,
                returncode=0,
                decision_path=run_dir / "decision.json",
            ),
            access_log_dir=runs_root,
        )
        records.append(
            record.model_copy(
                update={
                    "case_class": oracle.case_class.value,
                    "expected_state": oracle.expected_initial_state.value,
                }
            )
        )

    return records


def _account(
    record: RunRecord,
    provider: ModelProvider | None,
    ledger: BudgetLedger | None,
    max_total_tokens: int | None,
) -> RunRecord:
    """Fold the ledger into the record; invalidate a run that crossed the ceiling.

    Invalidation is at the record level: the run directory keeps its artifacts,
    because hiding what an over-budget run did would be worse than counting it.
    It just cannot count as a result, in either arm's favour.
    """
    if ledger is None or provider is None:
        return record
    record = record.model_copy(
        update={
            "provider": provider.name,
            "model": "+".join(sorted({call.model for call in ledger.calls})),
            "input_tokens": ledger.total_input_tokens,
            "output_tokens": ledger.total_output_tokens,
            "cost_usd_micros": ledger.total_cost_usd_micros,
            "model_calls": len(ledger.calls),
        }
    )
    if ledger.exceeded:
        record = record.model_copy(
            update={
                "outcome": ExternalState.EVIDENCE_INCOMPLETE.value,
                "marked_ready": False,
                "evidence_incomplete": True,
                "note": (
                    f"invalidated: token budget exceeded "
                    f"({ledger.total_tokens} > {max_total_tokens})"
                ),
            }
        )
    return record


def _run_final(
    arm: str,
    case_id: str,
    repeat: int,
    case_path: Path,
    run_dir: Path,
    clock: float,
    provider: ModelProvider | None,
) -> RunRecord:
    cert, _ = review_case(
        case_path,
        runs_root=run_dir.parent,
        run_id=run_dir.name,
        provider=provider,
        remediation_attempts=0,
    )
    state = cert.first_screen.external_state
    metrics_path = run_dir / "metrics.json"
    model_calls = 0
    if metrics_path.is_file():
        model_calls = int(json.loads(metrics_path.read_text()).get("model_calls", 0))
    # With no provider passed, review_case served the agents from recorded
    # fixtures; the run's own record of how calls were served is run.json.
    provider_label = ""
    run_json = run_dir / "run.json"
    if provider is None and run_json.is_file():
        provider_label = str(json.loads(run_json.read_text()).get("provider_mode", ""))

    return RunRecord(
        arm=arm,
        case_id=case_id,
        repeat=repeat,
        outcome=state,
        marked_ready=state in MARKED_READY_FINAL,
        evidence_incomplete=state == ExternalState.EVIDENCE_INCOMPLETE.value,
        asked_for_authority=state == ExternalState.DOMAIN_RULING_REQUIRED.value,
        provider=provider_label,
        duration_ms=int((time.monotonic() - clock) * 1000),
        model_calls=model_calls,
        note=cert.first_screen.decisive_invariant,
    )


def _run_baseline(
    arm: str,
    case_id: str,
    repeat: int,
    case_path: Path,
    run_dir: Path,
    clock: float,
    provider: ModelProvider | None,
) -> RunRecord:
    loaded = load_case(case_path)
    run_dir.mkdir(parents=True, exist_ok=True)

    if arm == ARM_VISIBLE_TESTS:
        decision = review_by_visible_tests(loaded)
        model_calls = 0
    else:
        if provider is None:
            raise EvidenceIncompleteError(
                "the direct-review baseline needs a provider",
                detail={"arm": arm, "case_id": case_id},
            )
        candidate = (loaded.benchmark_root / loaded.case.candidate.migration_path).read_text(
            encoding="utf-8"
        )
        decision = review_by_agent(loaded, provider=provider, candidate_sql=candidate)
        model_calls = 1

    (run_dir / "decision.json").write_bytes(canonical_json(decision.model_dump(mode="json")))
    (run_dir / "run.json").write_bytes(
        canonical_json(
            {
                "run_kind": "baseline",
                "arm": arm,
                "case_id": case_id,
                "provider_mode": provider.mode if provider is not None else "none",
                "inputs_digest": loaded.inputs_digest,
                "recorded_at": datetime.now(UTC).isoformat(),
            }
        )
    )

    return RunRecord(
        arm=arm,
        case_id=case_id,
        repeat=repeat,
        outcome=decision.decision,
        marked_ready=decision.decision in MARKED_READY_BASELINE,
        evidence_incomplete=False,
        asked_for_authority=decision.decision == "clarify",
        duration_ms=int((time.monotonic() - clock) * 1000),
        model_calls=model_calls,
        note=decision.rationale[:200],
    )
