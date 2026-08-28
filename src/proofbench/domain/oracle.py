"""Evaluator-only expectations.

This model exists so the answer key has a shape, but the module that *loads* it
lives in ``proofbench.evaluation`` and is importable from nowhere else. A model
definition carries no answers; a loader does.

``case_class`` is an enum rather than an ``is_unsafe`` boolean because C04 is
neither safe nor unsafe: it is a case whose correct outcome is that a human is
asked. A boolean cannot say that, and forcing it to try would misreport the one
case that tests the authority boundary.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal

from pydantic import Field

from proofbench.domain.base import StrictModel
from proofbench.domain.decision import ExternalState

ORACLE_SCHEMA_VERSION: Final[Literal["1.0"]] = "1.0"


class CaseClass(StrEnum):
    """What a case is for.

    Drives the metric denominators: only ``UNSAFE`` cases count toward the
    unsafe escape rate, only ``SAFE`` cases toward safe acceptance.
    """

    UNSAFE = "unsafe"
    SAFE = "safe"
    AUTHORITY_REQUIRED = "authority_required"


class BlastRadiusAssertion(StrictModel):
    """One impact the evaluator expects a correct run to have confirmed."""

    invariant_id: str
    role: str
    affected_tenant: str
    minimum_rows: int = Field(ge=0)


class OracleSpec(StrictModel):
    """The expected outcome for one case. Never readable by product code."""

    schema_version: Literal["1.0"]
    case_id: str = Field(pattern=r"^C\d{2}$")
    case_class: CaseClass
    expected_initial_state: ExternalState
    expected_blocking_invariant_ids: list[str] = Field(default_factory=list)
    expected_blast_radius_assertions: list[BlastRadiusAssertion] = Field(default_factory=list)
    rationale: str = Field(min_length=1)
