"""Product states and run discriminators.

The four external states are the product's entire public vocabulary (PRD section 7).
Their wire strings are pinned by test; renaming one breaks every committed artifact.
"""

from __future__ import annotations

from enum import StrEnum


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
