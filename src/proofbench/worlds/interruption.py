"""Interruption and resume world (PRD-FR-034).

A backfill is interrupted far more often than anyone plans for: a deploy is
cancelled, a pod is evicted, a connection drops. What matters is what happens
when it starts again.

The world runs the declared backfill a second time, which is what a resumed
backfill does when nothing recorded how far it got. A backfill that tracks its
own progress is unchanged by the second run. One that does not will duplicate,
and with money that duplication is a second payment.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import psycopg
from psycopg import sql

from proofbench.domain.evidence import CheckResult, EvidenceFailure, Finding, WorldResult
from proofbench.worlds.base import World, WorldRequest
from proofbench.worlds.common import check, finish, missing_configuration

WORLD_NAME = "interruption"
IDEMPOTENCE_INVARIANT = "INV-IDEM-001"


class InterruptionWorld(World):
    """Re-runs a backfill and requires the observable state to be unchanged."""

    name = WORLD_NAME
    threatened_invariants = (IDEMPOTENCE_INVARIANT,)

    def run(self, request: WorldRequest) -> WorldResult:
        started, clock = datetime.now(UTC), time.monotonic()
        checks: list[CheckResult] = []
        findings: list[Finding] = []
        failures: list[EvidenceFailure] = []

        spec = request.backfill
        if spec is None:
            failures.append(missing_configuration(WORLD_NAME, "a backfill specification"))
            return finish(self.name, self.threatened_invariants, started, clock, [], [], failures)

        observe = sql.SQL("SELECT {cols} FROM {table} ORDER BY 1").format(
            cols=sql.SQL(", ").join(sql.Identifier(c) for c in spec.observe_columns),
            table=sql.Identifier(spec.observe_table),
        )

        try:
            with psycopg.connect(request.dsn(spec.role)) as conn:
                before = conn.execute(observe).fetchall()
                conn.execute(spec.statement)
                conn.commit()
                after = conn.execute(observe).fetchall()
        except psycopg.Error as exc:
            failures.append(
                EvidenceFailure(
                    stage=f"world:{WORLD_NAME}",
                    reason="the backfill could not be resumed",
                    causes=[f"sqlstate={exc.sqlstate}", str(exc)[:200]],
                )
            )
            return finish(self.name, self.threatened_invariants, started, clock, [], [], failures)

        changed = before != after
        checks.append(
            check(
                "interruption:resume-is-a-no-op",
                f"re-run the backfill and compare {spec.observe_table}",
                failed=changed,
                clock=clock,
                invariant=IDEMPOTENCE_INVARIANT,
                detail=f"{len(before)} row(s) before, {len(after)} after",
            )
        )

        if changed:
            findings.append(
                Finding(
                    invariant_id=IDEMPOTENCE_INVARIANT,
                    blocking=True,
                    summary=(
                        f"resuming the backfill changed {spec.observe_table}: "
                        f"{len(before)} row(s) became {len(after)}"
                    ),
                    expected="a resumed backfill leaves the observable state unchanged",
                    observed=f"{len(after) - len(before)} row(s) added or altered on the retry",
                    check_ids=["interruption:resume-is-a-no-op"],
                )
            )
        return finish(self.name, self.threatened_invariants, started, clock, checks, findings, [])
