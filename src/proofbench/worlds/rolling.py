"""Rolling compatibility world (PRD-FR-033).

During a rolling deploy both application versions are live at once. A migration
that only makes sense once every instance has restarted is a migration that
breaks production for as long as the rollout takes.

Each version's declared statements run against the migrated schema as the role
that version uses. A statement the case marked ``must_succeed`` that raises is a
compatibility failure, and the SQLSTATE says exactly how.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import psycopg
from psycopg import sql

from proofbench.domain.evidence import CheckResult, EvidenceFailure, Finding, WorldResult
from proofbench.worlds.base import World, WorldRequest
from proofbench.worlds.common import check, finish, missing_configuration

WORLD_NAME = "rolling"
COMPAT_INVARIANT = "INV-COMPAT-001"


class RollingWorld(World):
    """Interleaves the declared statements of every live application version."""

    name = WORLD_NAME
    threatened_invariants = (COMPAT_INVARIANT,)

    def run(self, request: WorldRequest) -> WorldResult:
        started, clock = datetime.now(UTC), time.monotonic()
        checks: list[CheckResult] = []
        findings: list[Finding] = []
        failures: list[EvidenceFailure] = []

        if not request.app_versions:
            failures.append(missing_configuration(WORLD_NAME, "app_versions"))
            return finish(self.name, self.threatened_invariants, started, clock, [], [], failures)

        broken: list[str] = []
        for version in request.app_versions:
            for statement in version.statements:
                check_id = f"rolling:{version.version}:{statement.label}"
                sqlstate: str | None = None
                detail: str | None = None
                try:
                    with psycopg.connect(request.dsn(statement.role)) as conn, conn.cursor() as cur:
                        cur.execute(
                            sql.SQL("SET LOCAL aidledger.org_id = {}").format(
                                sql.Literal(str(statement.tenant))
                            )
                        )
                        cur.execute(statement.sql)
                        # Never committed: the world measures compatibility, it
                        # does not leave the database changed for the next one.
                        conn.rollback()
                except psycopg.Error as exc:
                    sqlstate = exc.sqlstate
                    detail = str(exc)[:200]

                failed = statement.must_succeed and sqlstate is not None
                if failed:
                    broken.append(f"{version.version}/{statement.label} ({sqlstate})")
                checks.append(
                    check(
                        check_id,
                        f"{version.version}: {statement.label}",
                        failed=failed,
                        clock=clock,
                        invariant=COMPAT_INVARIANT,
                        sqlstate=sqlstate,
                        detail=detail,
                    )
                )

        if broken:
            findings.append(
                Finding(
                    invariant_id=COMPAT_INVARIANT,
                    blocking=True,
                    summary=(
                        f"{len(broken)} statement(s) a live application version issues no "
                        "longer work against the migrated schema"
                    ),
                    expected="both versions keep working throughout the rollout",
                    observed="; ".join(broken),
                    check_ids=[c.check_id for c in checks if c.status.value == "failed"],
                )
            )
        return finish(self.name, self.threatened_invariants, started, clock, checks, findings, [])
