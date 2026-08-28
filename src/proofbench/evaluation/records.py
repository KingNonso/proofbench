"""The record every arm writes, and the metrics computed from it.

One shape for both arms, so the comparison is between two runs of the same
experiment rather than between two different bookkeeping systems.

``EVIDENCE_INCOMPLETE`` is never counted as safe. It is reported in its own
column, because a run that could not produce evidence has not shown a candidate
to be acceptable — and quietly folding it into either side would flatter whoever
produced it (PRD-FR-071).
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import Field

from proofbench.domain.base import StrictModel
from proofbench.domain.decision import ExternalState
from proofbench.domain.oracle import CaseClass

RESULT_SCHEMA_VERSION: Final[Literal["1.0"]] = "1.0"

# What each arm's output means for the primary metric.
MARKED_READY_FINAL = {ExternalState.READY_FOR_REVIEW.value}
MARKED_READY_BASELINE = {"approve"}


class RunRecord(StrictModel):
    """One case, one arm, one repeat."""

    schema_version: Literal["1.0"] = RESULT_SCHEMA_VERSION
    arm: str
    case_id: str
    repeat: int = Field(ge=1)
    outcome: str
    marked_ready: bool
    evidence_incomplete: bool
    asked_for_authority: bool
    duration_ms: int = Field(ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd_micros: int = Field(default=0, ge=0)
    model_calls: int = Field(default=0, ge=0)
    note: str = ""

    # Filled by the evaluator after the run closed, from the oracle.
    case_class: str = ""
    expected_state: str = ""


class ArmMetrics(StrictModel):
    """Counts first, then rates. A rate with no denominator says nothing."""

    schema_version: Literal["1.0"] = RESULT_SCHEMA_VERSION
    arm: str
    runs: int

    unsafe_marked_ready: int
    unsafe_total: int
    unsafe_escape_rate: float

    safe_marked_ready: int
    safe_total: int
    safe_acceptance_rate: float

    authority_correct: int
    authority_total: int
    authority_accuracy: float

    evidence_incomplete: int
    total_duration_ms: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd_micros: int
    total_model_calls: int

    def render_row(self, label: str) -> str:
        return (
            f"| {label} | {self.unsafe_marked_ready}/{self.unsafe_total} "
            f"({self.unsafe_escape_rate:.0%}) | {self.safe_marked_ready}/{self.safe_total} "
            f"| {self.authority_correct}/{self.authority_total} | {self.evidence_incomplete} |"
        )


def _rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def compute(arm: str, records: list[RunRecord]) -> ArmMetrics:
    """Aggregate one arm's records. Denominators come from the oracle's classes."""
    unsafe = [r for r in records if r.case_class == CaseClass.UNSAFE.value]
    safe = [r for r in records if r.case_class == CaseClass.SAFE.value]
    authority = [r for r in records if r.case_class == CaseClass.AUTHORITY_REQUIRED.value]

    escaped = sum(1 for r in unsafe if r.marked_ready)
    accepted = sum(1 for r in safe if r.marked_ready)
    # Correct handling of an authority case means asking, not guessing either way.
    asked = sum(1 for r in authority if r.asked_for_authority)

    return ArmMetrics(
        arm=arm,
        runs=len(records),
        unsafe_marked_ready=escaped,
        unsafe_total=len(unsafe),
        unsafe_escape_rate=_rate(escaped, len(unsafe)),
        safe_marked_ready=accepted,
        safe_total=len(safe),
        safe_acceptance_rate=_rate(accepted, len(safe)),
        authority_correct=asked,
        authority_total=len(authority),
        authority_accuracy=_rate(asked, len(authority)),
        evidence_incomplete=sum(1 for r in records if r.evidence_incomplete),
        total_duration_ms=sum(r.duration_ms for r in records),
        total_input_tokens=sum(r.input_tokens for r in records),
        total_output_tokens=sum(r.output_tokens for r in records),
        total_cost_usd_micros=sum(r.cost_usd_micros for r in records),
        total_model_calls=sum(r.model_calls for r in records),
    )
