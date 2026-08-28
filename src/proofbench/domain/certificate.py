"""The Migration Change Certificate.

One typed record; JSON is canonical and Markdown and HTML are projections of it.
Rendering from a single model is what stops the three formats disagreeing about
the decision, which would be the worst possible bug in a document whose only job
is to say what happened.

The first screen is fixed by PRD-FR-060 and is not a summary the renderer may
rearrange: a reviewer must reach state, change, decisive invariant, blast radius,
next action, ruling, and replay command without scrolling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Final, Literal

from pydantic import Field

from proofbench.domain.base import StrictModel
from proofbench.domain.decision import BlastRadiusItem, DecisionRecord
from proofbench.domain.evidence import CheckResult, WorldResult

CERTIFICATE_SCHEMA_VERSION: Final[Literal["1.0"]] = "1.0"
MANIFEST_SCHEMA_VERSION: Final[Literal["1.0"]] = "1.0"


class FirstScreen(StrictModel):
    """The seven fields a reviewer must see immediately (PRD-FR-060)."""

    external_state: str
    candidate_change: str
    decisive_invariant: str
    confirmed_blast_radius: list[BlastRadiusItem] = Field(default_factory=list)
    required_action: str
    human_ruling: str | None = None
    replay_command: str


class EnvironmentRecord(StrictModel):
    """What this run actually executed on."""

    python_version: str
    platform: str
    postgres_image: str
    resolved_image_id: str | None = None
    timezone: str


class TrajectorySummary(StrictModel):
    """A readable account of the run, compiled from trace events."""

    events: int
    trace_root_hash: str
    stages: list[str] = Field(default_factory=list)
    narrative: list[str] = Field(default_factory=list)


class ArtifactHash(StrictModel):
    """One artifact and the digest of its exact stored bytes."""

    name: str
    sha256: str
    bytes: int


class RunManifest(StrictModel):
    """Hashes every artifact produced before it.

    Written last, and deliberately not referenced by digest from the certificate:
    a manifest that hashed the certificate while the certificate embedded the
    manifest's hash could never be verified at all.
    """

    schema_version: Literal["1.0"] = MANIFEST_SCHEMA_VERSION
    run_id: str
    case_id: str
    run_kind: str
    provider_mode: str
    created_at: datetime
    inputs_digest: str
    inputs: list[ArtifactHash] = Field(default_factory=list)
    artifacts: list[ArtifactHash] = Field(default_factory=list)
    policy_hash: str
    prompt_hashes: dict[str, str] = Field(default_factory=dict)
    trace_root_hash: str
    world_semantic_digests: dict[str, str] = Field(default_factory=dict)
    decision_state: str
    environment: EnvironmentRecord
    evaluator_version: str
    replay_command: str


class MigrationChangeCertificate(StrictModel):
    """The finished artifact a reviewer reads."""

    schema_version: Literal["1.0"] = CERTIFICATE_SCHEMA_VERSION
    run_id: str
    case_id: str
    case_title: str
    generated_at: datetime
    run_kind: str
    provider_mode: str

    first_screen: FirstScreen

    # Detail sections.
    decision: DecisionRecord
    world_results: list[WorldResult] = Field(default_factory=list)
    visible_tests: list[CheckResult] = Field(default_factory=list)
    trajectory: TrajectorySummary
    environment: EnvironmentRecord
    inputs_digest: str
    known_limits: list[str] = Field(default_factory=list)
    manifest_path: str = "manifest.json"

    def semantic_projection(self) -> dict[str, object]:
        """What a replay must reproduce.

        Excludes timing and the run id, which differ by construction on a rerun,
        and keeps the decision, the decisive checks, the confirmed impacts, and
        each world's own semantic digest.
        """
        return {
            "case_id": self.case_id,
            "decision_state": self.decision.external_state.value,
            "decisive_check_ids": sorted(self.decision.decisive_check_ids),
            "evidence_complete": self.decision.evidence_complete,
            "confirmed": [
                {
                    "invariant_id": item.invariant_id,
                    "role": item.role,
                    "operation": item.operation,
                    "affected_tenant": item.affected_tenant,
                    "rows_affected": item.rows_affected,
                    "row_keys": sorted(item.row_keys),
                }
                for item in self.decision.confirmed
            ],
            "worlds": {result.world: result.semantic_digest for result in self.world_results},
            "visible_tests": [
                {"check_id": check.check_id, "status": check.status.value}
                for check in self.visible_tests
            ],
        }
