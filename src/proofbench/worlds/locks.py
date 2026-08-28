"""Lock and availability world (PRD-FR-036).

The question is not whether a migration takes an exclusive lock. Every
``ALTER TABLE`` does, including the safe ones, so a contention test alone would
condemn the correct migration alongside the reckless one. The question is how
long it holds that lock, and that is decided by whether the statement rewrites
the table.

PostgreSQL answers it exactly: a rewrite gives the relation a new filenode. A
metadata-only change does not. That fact is identical on every machine and
independent of how large the table happens to be in a fixture, which a stopwatch
could never be.

Elapsed time and SQLSTATE are recorded as supporting evidence. Neither decides.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import psycopg
from psycopg import sql

from proofbench.domain.evidence import CheckResult, EvidenceFailure, Finding, WorldResult
from proofbench.worlds.base import World, WorldRequest
from proofbench.worlds.common import check, finish, missing_configuration

WORLD_NAME = "locks"
LOCK_INVARIANT = "INV-LOCK-001"
LOCK_NOT_AVAILABLE = "55P03"


class LocksWorld(World):
    """Fails a statement that rewrites the table, or that cannot get its lock."""

    name = WORLD_NAME
    threatened_invariants = (LOCK_INVARIANT,)

    def run(self, request: WorldRequest) -> WorldResult:
        started, clock = datetime.now(UTC), time.monotonic()
        checks: list[CheckResult] = []
        findings: list[Finding] = []
        failures: list[EvidenceFailure] = []

        probe = request.lock_probe
        if probe is None:
            failures.append(missing_configuration(WORLD_NAME, "a lock probe"))
            return finish(self.name, self.threatened_invariants, started, clock, [], [], failures)

        filenode = sql.SQL("SELECT pg_relation_filenode({table})").format(
            table=sql.Literal(probe.target_table)
        )
        sqlstate: str | None = None
        elapsed_ms = 0

        try:
            with psycopg.connect(request.dsn(probe.role)) as conn:
                before = conn.execute(filenode).fetchone()
                after = before
                began = time.monotonic()
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            sql.SQL("SET LOCAL lock_timeout = {}").format(
                                sql.Literal(f"{request.lock_budget_ms}ms")
                            )
                        )
                        cur.execute(probe.statement)
                    elapsed_ms = int((time.monotonic() - began) * 1000)
                    after = conn.execute(filenode).fetchone()
                except psycopg.Error as exc:
                    sqlstate = exc.sqlstate
                    elapsed_ms = int((time.monotonic() - began) * 1000)
                # Never committed: the world measures the statement, it does not
                # apply it.
                conn.rollback()
        except psycopg.Error as exc:
            failures.append(
                EvidenceFailure(
                    stage=f"world:{WORLD_NAME}",
                    reason="the lock probe could not be set up",
                    causes=[f"sqlstate={exc.sqlstate}", str(exc)[:200]],
                )
            )
            return finish(self.name, self.threatened_invariants, started, clock, [], [], failures)

        if sqlstate is not None and sqlstate != LOCK_NOT_AVAILABLE:
            failures.append(
                EvidenceFailure(
                    stage=f"world:{WORLD_NAME}",
                    reason="the statement failed for a reason unrelated to locking",
                    causes=[f"sqlstate={sqlstate}"],
                )
            )
            return finish(self.name, self.threatened_invariants, started, clock, [], [], failures)

        timed_out = sqlstate == LOCK_NOT_AVAILABLE
        node_before = before[0] if before else None
        node_after = after[0] if after else None
        rewrote = not timed_out and node_before != node_after

        checks.append(
            check(
                "locks:no-table-rewrite",
                f"compare pg_relation_filenode({probe.target_table}) across the statement",
                failed=rewrote,
                clock=clock,
                invariant=LOCK_INVARIANT,
                detail=f"elapsed {elapsed_ms}ms (evidence only; the verdict is the filenode)",
            )
        )
        checks.append(
            check(
                "locks:within-budget",
                f"run with lock_timeout={request.lock_budget_ms}ms",
                failed=timed_out,
                clock=clock,
                invariant=LOCK_INVARIANT,
                sqlstate=sqlstate,
            )
        )

        if rewrote:
            findings.append(
                Finding(
                    invariant_id=LOCK_INVARIANT,
                    blocking=True,
                    summary=(
                        f"the statement rewrites {probe.target_table}, holding ACCESS "
                        "EXCLUSIVE for the whole rewrite"
                    ),
                    expected="a metadata-only change that takes its lock and returns",
                    observed=f"relation filenode changed from {node_before} to {node_after}",
                    check_ids=["locks:no-table-rewrite"],
                )
            )
        if timed_out:
            findings.append(
                Finding(
                    invariant_id=LOCK_INVARIANT,
                    blocking=True,
                    summary=(
                        f"the statement could not acquire its lock within the declared "
                        f"{request.lock_budget_ms}ms budget"
                    ),
                    expected=f"lock acquired within {request.lock_budget_ms}ms",
                    observed=f"SQLSTATE {LOCK_NOT_AVAILABLE}, lock not available",
                    check_ids=["locks:within-budget"],
                )
            )
        return finish(self.name, self.threatened_invariants, started, clock, checks, findings, [])
