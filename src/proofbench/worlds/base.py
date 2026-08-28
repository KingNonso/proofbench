"""World interface and the request a world executes.

A world receives a fully-resolved, serialisable request and returns typed
evidence. It never reads a case file, never opens a Docker socket, and never
holds an administrative connection: everything it needs is in the request, which
is what lets it run in a spawned child that inherits nothing.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import Field

from proofbench.domain.base import StrictModel
from proofbench.domain.case import (
    AppStatement,
    AppVersion,
    BackfillSpec,
    LockProbeSpec,
    RlsProbeSpec,
)
from proofbench.domain.evidence import WorldResult
from proofbench.domain.ruling import CompiledRuling


class ProbeTarget(StrictModel):
    """A probe plus the fixture fact the parent verified before spawning.

    ``target_row_count`` is measured by the parent under an administrative
    connection. Without it a ``deny_empty`` probe is vacuous: zero rows returned
    proves the tenant boundary held only if there were rows on the other side to
    withhold.
    """

    probe: RlsProbeSpec
    target_row_count: int = Field(ge=0)


class PaymentSnapshotRow(StrictModel):
    """One row as it stood *before* the candidate applied.

    Measured by the parent under an administrative connection. Without a before
    state a money world can see that a value is now USD but not whether the
    migration is what made it so, nor whether it touched rows outside its scope.
    """

    payment_id: str
    org_id: str
    currency_code: str | None
    amount_minor: int


class DisbursementSnapshotRow(StrictModel):
    """One settled disbursement as it stood before the candidate applied."""

    disbursement_id: str
    payment_id: str
    amount_minor: int


class AuditSnapshotRow(StrictModel):
    """One audit event as it stood before the candidate applied."""

    event_id: int
    org_id: str
    actor_role: str
    action: str
    entity_id: str


class WorldRequest(StrictModel):
    """Everything a world needs, and nothing it does not.

    Wide rather than generic on purpose. A world receives the configuration its
    own checks require and nothing else, so reading the request tells you what
    that world can possibly do.
    """

    world: str
    run_id: str
    host: str
    port: int
    database: str
    # Role name to password. Only the roles this world probes; no admin role.
    credentials: dict[str, str]
    targets: list[ProbeTarget] = Field(default_factory=list)
    compiled_ruling: CompiledRuling | None = None
    pre_state: list[PaymentSnapshotRow] = Field(default_factory=list)
    pre_audit: list[AuditSnapshotRow] = Field(default_factory=list)
    pre_disbursements: list[DisbursementSnapshotRow] = Field(default_factory=list)
    app_versions: list[AppVersion] = Field(default_factory=list)
    backfill: BackfillSpec | None = None
    lock_probe: LockProbeSpec | None = None
    lock_budget_ms: int = Field(default=250, gt=0)
    rollback_sql: str | None = None
    post_migration_write: AppStatement | None = None
    deadline_seconds: int = Field(gt=0)

    def dsn(self, user: str) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.database} "
            f"user={user} password={self.credentials[user]} connect_timeout=10"
        )


class World(ABC):
    """One deterministic migration world."""

    name: str
    threatened_invariants: tuple[str, ...]

    @abstractmethod
    def run(self, request: WorldRequest) -> WorldResult:
        """Execute the world and return typed evidence. Never raises for a
        finding; a finding is a result, not an error."""
