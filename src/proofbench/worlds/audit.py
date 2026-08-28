"""Audit history world (PRD-FR-037).

Audit history is the record you consult precisely when something has gone wrong,
which is the worst possible time to discover a migration edited it. The table is
append-only by grant, so a migration that removes or rewrites events had to run
as a role that could — and the only role that can is the one applying it.

Comparison is against the snapshot taken before the candidate applied. Counting
rows afterwards would not notice a deletion and an insertion that happen to
balance.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import psycopg

from proofbench.domain.evidence import CheckResult, EvidenceFailure, Finding, WorldResult
from proofbench.sandbox.postgres import MIGRATION_ROLE
from proofbench.worlds.base import World, WorldRequest
from proofbench.worlds.common import check, finish

WORLD_NAME = "audit"
AUDIT_INVARIANT = "INV-AUDIT-001"


class AuditWorld(World):
    """Requires every recorded event to still be present and unaltered."""

    name = WORLD_NAME
    threatened_invariants = (AUDIT_INVARIANT,)

    def run(self, request: WorldRequest) -> WorldResult:
        started, clock = datetime.now(UTC), time.monotonic()
        checks: list[CheckResult] = []
        findings: list[Finding] = []
        failures: list[EvidenceFailure] = []

        if not request.pre_audit:
            failures.append(
                EvidenceFailure(
                    stage=f"world:{WORLD_NAME}",
                    reason="no pre-migration audit snapshot; nothing can be compared",
                )
            )
            return finish(self.name, self.threatened_invariants, started, clock, [], [], failures)

        try:
            with psycopg.connect(request.dsn(MIGRATION_ROLE)) as conn:
                rows = conn.execute(
                    "SELECT event_id, org_id, actor_role, action, entity_id FROM audit_events"
                ).fetchall()
        except psycopg.Error as exc:
            failures.append(
                EvidenceFailure(
                    stage=f"world:{WORLD_NAME}",
                    reason="could not read audit history after the migration",
                    causes=[f"sqlstate={exc.sqlstate}", str(exc)[:200]],
                )
            )
            return finish(self.name, self.threatened_invariants, started, clock, [], [], failures)

        after = {int(row[0]): (str(row[1]), str(row[2]), str(row[3]), str(row[4])) for row in rows}
        before = {
            row.event_id: (row.org_id, row.actor_role, row.action, row.entity_id)
            for row in request.pre_audit
        }

        removed = sorted(set(before) - set(after))
        mutated = sorted(
            event_id
            for event_id, value in before.items()
            if event_id in after and after[event_id] != value
        )

        checks.append(
            check(
                "audit:events-still-present",
                "compare recorded audit events before and after the migration",
                failed=bool(removed),
                clock=clock,
                invariant=AUDIT_INVARIANT,
                detail=f"{len(before)} before, {len(after)} after",
            )
        )
        checks.append(
            check(
                "audit:events-unaltered",
                "compare the content of every surviving audit event",
                failed=bool(mutated),
                clock=clock,
                invariant=AUDIT_INVARIANT,
            )
        )

        if removed or mutated:
            parts = []
            if removed:
                parts.append(f"{len(removed)} event(s) removed: {removed[:5]}")
            if mutated:
                parts.append(f"{len(mutated)} event(s) altered: {mutated[:5]}")
            findings.append(
                Finding(
                    invariant_id=AUDIT_INVARIANT,
                    blocking=True,
                    summary="the migration changed audit history",
                    expected="audit events are append-only; nothing is removed or rewritten",
                    observed="; ".join(parts),
                    check_ids=["audit:events-still-present", "audit:events-unaltered"],
                )
            )
        return finish(self.name, self.threatened_invariants, started, clock, checks, findings, [])
