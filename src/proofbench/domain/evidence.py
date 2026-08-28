"""Typed evidence: what a world observed, and what it concluded.

No world ever returns prose. Every conclusion resolves to a ``CheckResult`` that
records what ran, what happened, and which SQLSTATE came back, so a finding can
always be traced to an executed command (PRD-FR-030).

The distinction that matters most here is between *denial* and *error*. Under
row-level security a denial is usually zero rows, not an exception. A probe that
blew up on a typo and a probe that was correctly filtered look nothing alike, and
collapsing them would let a broken world read as a clean pass.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Final, Literal

from pydantic import Field

from proofbench.domain.base import StrictModel
from proofbench.tracing.hashes import digest_json

EVIDENCE_SCHEMA_VERSION: Final[Literal["1.0"]] = "1.0"


class CheckStatus(StrEnum):
    """Outcome of a single executed check.

    ``ERROR`` and ``TIMEOUT`` are kept apart from ``FAILED`` because they mean
    different things to the decision policy: a failure blocks, while an error or
    a timeout means no trustworthy evidence was produced at all.
    """

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"


class WorldStatus(StrEnum):
    """Outcome of a whole world."""

    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"


class CheckResult(StrictModel):
    """One executed check. PRD-FR-030 requires all of these fields."""

    schema_version: Literal["1.0"] = EVIDENCE_SCHEMA_VERSION
    check_id: str = Field(min_length=1)
    # Sanitized: the parameterized statement, never the bound credential or a
    # host path. Redaction happens before this is constructed.
    command: str = Field(min_length=1)
    status: CheckStatus
    duration_ms: int = Field(ge=0)
    sqlstate: str | None = None
    evidence_ref: str | None = None
    blocking_class: str | None = None
    detail: str | None = None


class AccessObservation(StrictModel):
    """What one role actually saw or changed.

    This is the unit that makes a blast radius *confirmed*: it names a role, a
    tenant, an operation, and the specific rows involved.
    """

    schema_version: Literal["1.0"] = EVIDENCE_SCHEMA_VERSION
    probe_id: str
    role: str
    table: str
    operation: str
    scope: str
    session_tenant: str
    target_tenant: str
    permitted_by_policy: bool
    observed_allowed: bool
    rows_seen: int = Field(ge=0)
    row_keys: list[str] = Field(default_factory=list)
    sqlstate: str | None = None


class Finding(StrictModel):
    """A conclusion, derived only from observations that actually executed."""

    schema_version: Literal["1.0"] = EVIDENCE_SCHEMA_VERSION
    invariant_id: str
    blocking: bool
    summary: str
    expected: str
    observed: str
    check_ids: list[str] = Field(default_factory=list)
    observations: list[AccessObservation] = Field(default_factory=list)


class EvidenceFailure(StrictModel):
    """Why trustworthy evidence could not be produced.

    Carries a list of causes rather than one, because a world that failed and
    then failed to clean up has two facts worth keeping and neither replaces the
    other.
    """

    schema_version: Literal["1.0"] = EVIDENCE_SCHEMA_VERSION
    stage: str
    reason: str
    causes: list[str] = Field(default_factory=list)


class WorldResult(StrictModel):
    """Everything one world produced."""

    schema_version: Literal["1.0"] = EVIDENCE_SCHEMA_VERSION
    world: str
    status: WorldStatus
    threatened_invariants: list[str] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    observations: list[AccessObservation] = Field(default_factory=list)
    failures: list[EvidenceFailure] = Field(default_factory=list)
    started_at: datetime
    ended_at: datetime
    duration_ms: int = Field(ge=0)
    semantic_digest: str = ""

    def semantic_projection(self) -> dict[str, Any]:
        """The part of this result that must be identical on a replay.

        Timestamps, durations, and the digest itself are volatile and excluded.
        Executed row counts, SQLSTATEs, roles, tenants, and row keys are the
        evidence and are retained. Declared here, on the model that owns the
        fields, rather than in a shared set that would only ever grow until
        replay stopped detecting real differences.
        """
        return {
            "world": self.world,
            "status": self.status.value,
            "threatened_invariants": sorted(self.threatened_invariants),
            "checks": [
                {
                    "check_id": check.check_id,
                    "command": check.command,
                    "status": check.status.value,
                    "sqlstate": check.sqlstate,
                    "blocking_class": check.blocking_class,
                }
                for check in self.checks
            ],
            "findings": [
                {
                    "invariant_id": finding.invariant_id,
                    "blocking": finding.blocking,
                    "expected": finding.expected,
                    "observed": finding.observed,
                    "check_ids": sorted(finding.check_ids),
                }
                for finding in self.findings
            ],
            "observations": [
                {
                    "probe_id": item.probe_id,
                    "role": item.role,
                    "table": item.table,
                    "operation": item.operation,
                    "scope": item.scope,
                    "session_tenant": item.session_tenant,
                    "target_tenant": item.target_tenant,
                    "permitted_by_policy": item.permitted_by_policy,
                    "observed_allowed": item.observed_allowed,
                    "rows_seen": item.rows_seen,
                    "row_keys": sorted(item.row_keys),
                    "sqlstate": item.sqlstate,
                }
                for item in self.observations
            ],
            "failures": [
                {"stage": failure.stage, "reason": failure.reason} for failure in self.failures
            ],
        }

    def with_digest(self) -> WorldResult:
        """Return a copy carrying the semantic digest of its own projection."""
        return self.model_copy(
            update={"semantic_digest": digest_json(self.semantic_projection(), reject_floats=True)}
        )

    def has_blocking_finding(self) -> bool:
        return any(finding.blocking for finding in self.findings)
