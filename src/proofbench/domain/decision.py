"""Product states and run discriminators.

The four external states are the product's entire public vocabulary (PRD section 7).
Their wire strings are pinned by test; renaming one breaks every committed artifact.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal

from pydantic import Field

from proofbench.domain.base import StrictModel


class ExternalState(StrEnum):
    """The single state a completed run reports."""

    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    BLOCKED = "BLOCKED"
    DOMAIN_RULING_REQUIRED = "DOMAIN_RULING_REQUIRED"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"


class RunKind(StrEnum):
    """What produced a run directory.

    Artifact requirements are a discriminated union over this: a baseline run
    has no migration contract and no world plan, and validating it as though it
    did would reject a legitimate run.
    """

    BASELINE = "baseline"
    MIGRATION_COURT = "migration_court"
    REPLAY = "replay"


class ProviderMode(StrEnum):
    """How model calls were served, kept separate from RunKind.

    `none` is the honest value for a deterministic run that made no model call
    at all, which is what the whole offline judge path depends on.
    """

    LIVE = "live"
    FAKE = "fake"
    RECORDED = "recorded"
    NONE = "none"


DECISION_SCHEMA_VERSION: Final[Literal["1.0"]] = "1.0"


class BlastRadiusItem(StrictModel):
    """One impact, and the executed evidence that supports it.

    A confirmed item must name its check ids. An item with no executed evidence
    behind it belongs in ``possible``, which this slice keeps empty because it
    comes from contract analysis that does not exist yet. The two lists are never
    merged (PRD-FR-041).
    """

    schema_version: Literal["1.0"] = DECISION_SCHEMA_VERSION
    invariant_id: str
    role: str
    operation: str
    affected_tenant: str
    rows_affected: int = Field(ge=0)
    row_keys: list[str] = Field(default_factory=list)
    check_ids: list[str] = Field(default_factory=list)
    summary: str


class DecisionRecord(StrictModel):
    """The product's answer, and why.

    Produced by a pure function over typed evidence. No model output is an input
    to it, so no amount of agent prose can turn a failed blocking check into a
    pass (PRD-FR-040).
    """

    schema_version: Literal["1.0"] = DECISION_SCHEMA_VERSION
    external_state: ExternalState
    policy_version: int
    reasons: list[str] = Field(default_factory=list)
    decisive_check_ids: list[str] = Field(default_factory=list)
    confirmed: list[BlastRadiusItem] = Field(default_factory=list)
    possible: list[BlastRadiusItem] = Field(default_factory=list)
    required_action: str
    evidence_complete: bool
