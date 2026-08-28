"""Concurrent write and rollback world (PRD-FR-035).

A rollback is written for the schema, and tested on an idle database. Production
is not idle. Between the migration starting and someone deciding to roll it back,
the application keeps accepting work.

The world writes after the migration, rolls back, and asks whether that work
survived. A rollback that restores the old schema by discarding everything
written since is not a rollback; it is data loss with a reassuring name.

A rollback that cannot run at all is a finding about the candidate rather than an
error in this world, and it is the worst kind: nobody discovers it until they
already needed it.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import psycopg
from psycopg import sql

from proofbench.domain.evidence import CheckResult, EvidenceFailure, Finding, WorldResult
from proofbench.sandbox.postgres import MIGRATION_ROLE
from proofbench.worlds.base import World, WorldRequest
from proofbench.worlds.common import check, finish, missing_configuration

WORLD_NAME = "rollback"
ROLLBACK_INVARIANT = "INV-ROLLBACK-001"

# The row every case's post-migration write must create, so the world knows
# what to look for after the rollback runs.
POST_START_PAYMENT_ID = "99999999-0000-4000-8000-0000000000ff"


class RollbackWorld(World):
    """Writes after the migration begins, rolls back, and looks for the writes."""

    name = WORLD_NAME
    threatened_invariants = (ROLLBACK_INVARIANT,)

    def run(self, request: WorldRequest) -> WorldResult:
        started, clock = datetime.now(UTC), time.monotonic()
        checks: list[CheckResult] = []
        findings: list[Finding] = []
        failures: list[EvidenceFailure] = []

        if request.rollback_sql is None:
            failures.append(missing_configuration(WORLD_NAME, "a rollback script"))
            return finish(self.name, self.threatened_invariants, started, clock, [], [], failures)

        write = request.post_migration_write
        if write is None:
            failures.append(missing_configuration(WORLD_NAME, "a post-migration write"))
            return finish(self.name, self.threatened_invariants, started, clock, [], [], failures)

        try:
            with psycopg.connect(request.dsn(write.role)) as conn:
                # A write committed after the migration, using the schema the
                # migration just produced -- which is what the running
                # application would actually issue.
                conn.execute(
                    sql.SQL("SET LOCAL aidledger.org_id = {}").format(
                        sql.Literal(str(write.tenant))
                    )
                )
                conn.execute(write.sql)
                conn.commit()

            with psycopg.connect(request.dsn(MIGRATION_ROLE)) as conn:
                try:
                    conn.execute(request.rollback_sql)
                    conn.commit()
                except psycopg.Error as exc:
                    # The rollback script is the artifact under test. A rollback
                    # that raises is a finding about the candidate, not a failure
                    # of this world -- and it is the worst kind of finding,
                    # because it is discovered during an incident.
                    conn.rollback()
                    findings.append(
                        Finding(
                            invariant_id=ROLLBACK_INVARIANT,
                            blocking=True,
                            summary="the declared rollback could not run at all",
                            expected="the rollback executes and restores the previous shape",
                            observed=f"SQLSTATE {exc.sqlstate}: {str(exc)[:160]}",
                            check_ids=["rollback:script-runs"],
                        )
                    )
                    checks.append(
                        check(
                            "rollback:script-runs",
                            "execute the declared rollback script",
                            failed=True,
                            clock=clock,
                            invariant=ROLLBACK_INVARIANT,
                            sqlstate=exc.sqlstate,
                        )
                    )
                    return finish(
                        self.name, self.threatened_invariants, started, clock, checks, findings, []
                    )

                survivors = conn.execute(
                    sql.SQL("SELECT count(*) FROM payments WHERE payment_id = {pid}").format(
                        pid=sql.Literal(POST_START_PAYMENT_ID)
                    )
                ).fetchone()
        except psycopg.Error as exc:
            failures.append(
                EvidenceFailure(
                    stage=f"world:{WORLD_NAME}",
                    reason="the world could not reach the database to exercise the rollback",
                    causes=[f"sqlstate={exc.sqlstate}", str(exc)[:200]],
                )
            )
            return finish(self.name, self.threatened_invariants, started, clock, [], [], failures)

        lost = not survivors or int(survivors[0]) == 0
        checks.append(
            check(
                "rollback:post-start-write-survives",
                "write a payment after the migration, roll back, and look for it",
                failed=lost,
                clock=clock,
                invariant=ROLLBACK_INVARIANT,
                detail=f"payment {POST_START_PAYMENT_ID}",
            )
        )
        if lost:
            findings.append(
                Finding(
                    invariant_id=ROLLBACK_INVARIANT,
                    blocking=True,
                    summary=(
                        "a payment committed after the migration began did not survive rollback"
                    ),
                    expected="rollback restores the old schema and keeps the new rows",
                    observed=f"payment {POST_START_PAYMENT_ID} is absent after rollback",
                    check_ids=["rollback:post-start-write-survives"],
                )
            )
        return finish(self.name, self.threatened_invariants, started, clock, checks, findings, [])
