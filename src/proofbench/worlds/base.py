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
from proofbench.domain.case import RlsProbeSpec
from proofbench.domain.evidence import WorldResult


class ProbeTarget(StrictModel):
    """A probe plus the fixture fact the parent verified before spawning.

    ``target_row_count`` is measured by the parent under an administrative
    connection. Without it a ``deny_empty`` probe is vacuous: zero rows returned
    proves the tenant boundary held only if there were rows on the other side to
    withhold.
    """

    probe: RlsProbeSpec
    target_row_count: int = Field(ge=0)


class WorldRequest(StrictModel):
    """Everything a world needs, and nothing it does not."""

    world: str
    run_id: str
    host: str
    port: int
    database: str
    # Role name to password. Only the roles this world probes; no admin role.
    credentials: dict[str, str]
    targets: list[ProbeTarget] = Field(default_factory=list)
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
