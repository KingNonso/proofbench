"""Prepare and run the worlds a case requires.

The parent side of the boundary. It holds the administrative connection, so it
is the only thing that can measure the fixture before a world runs, and it is
the only thing that spawns the child. A world never sees any of this.

This is not the workflow state machine — it runs worlds and nothing else.
"""

from __future__ import annotations

import time
from pathlib import Path

import psycopg
from psycopg import sql

from proofbench.domain.case import AppVersion, ProbeOutcome, RlsProbeSpec
from proofbench.domain.evidence import CheckResult, CheckStatus, WorldResult
from proofbench.domain.ruling import CompiledRuling
from proofbench.domain.trace import EventType
from proofbench.errors import EvidenceIncompleteError
from proofbench.intake.loader import LoadedCase
from proofbench.sandbox.postgres import MIGRATION_ROLE, PostgresSandbox
from proofbench.sandbox.worker import run_world
from proofbench.tracing.writer import TraceWriter
from proofbench.worlds.base import (
    AuditSnapshotRow,
    DisbursementSnapshotRow,
    PaymentSnapshotRow,
    ProbeTarget,
    WorldRequest,
)


def prepare_world_database(sandbox: PostgresSandbox, loaded: LoadedCase, world: str) -> str:
    """Clone a fresh database and apply the candidate migration to it."""
    database = sandbox.clone(world)
    sandbox.apply_sql_file(
        database,
        loaded.benchmark_root / loaded.case.candidate.migration_path,
        user=MIGRATION_ROLE,
    )
    return database


def run_visible_tests(
    sandbox: PostgresSandbox, database: str, loaded: LoadedCase
) -> list[CheckResult]:
    """Run the case's visible tests.

    These are the checks a reviewer would naturally run. For an unsafe case they
    are expected to pass: if the obvious check caught the defect, the case would
    not be testing anything the deployment timeline adds.

    Assertions raise inside the SQL, so any exception is a failure and the
    SQLSTATE is kept as evidence.
    """
    results: list[CheckResult] = []
    for index, relative in enumerate(loaded.case.visible_tests):
        path = loaded.benchmark_root / relative
        clock = time.monotonic()
        sqlstate: str | None = None
        detail: str | None = None
        status = CheckStatus.PASSED
        try:
            sandbox.apply_sql_file(database, path, user=MIGRATION_ROLE)
        except psycopg.Error as exc:
            status = CheckStatus.FAILED
            sqlstate = exc.sqlstate
            detail = str(exc)[:300]
        results.append(
            CheckResult(
                check_id=f"visible:{index}:{Path(relative).name}",
                command=f"visible test {relative}",
                status=status,
                duration_ms=int((time.monotonic() - clock) * 1000),
                sqlstate=sqlstate,
                detail=detail,
            )
        )
    return results


def build_targets(
    sandbox: PostgresSandbox, database: str, probes: list[RlsProbeSpec]
) -> list[ProbeTarget]:
    """Measure how many rows each probe targets, under an admin connection.

    A ``deny_empty`` probe against an empty target set would report a clean pass
    while proving nothing, so the count is measured here and the world treats a
    zero as an evidence error.
    """
    targets: list[ProbeTarget] = []
    with sandbox.connect(database) as conn:
        for probe in probes:
            if probe.expected_outcome is ProbeOutcome.DENY_ERROR:
                # Privilege probes do not depend on data being present.
                targets.append(ProbeTarget(probe=probe, target_row_count=0))
                continue
            statement = sql.SQL("SELECT count(*) FROM {table} WHERE {pred}").format(
                table=sql.Identifier(probe.table),
                pred=sql.SQL(probe.predicate),  # noqa: S608 - validated policy fragment
            )
            row = conn.execute(statement, probe.values).fetchone()
            count = int(row[0]) if row and isinstance(row[0], int) else 0
            targets.append(ProbeTarget(probe=probe, target_row_count=count))
    return targets


def snapshot_payments(sandbox: PostgresSandbox, database: str) -> list[PaymentSnapshotRow]:
    """Capture payments before the candidate applies.

    Taken by the parent under an administrative connection, because a world that
    only sees the after state can tell that a value is USD but not whether the
    migration is what made it so.
    """
    with sandbox.connect(database) as conn:
        rows = conn.execute(
            "SELECT payment_id, org_id, currency_code, amount_minor FROM payments ORDER BY 1"
        ).fetchall()
    return [
        PaymentSnapshotRow(
            payment_id=str(row[0]),
            org_id=str(row[1]),
            currency_code=None if row[2] is None else str(row[2]).strip(),
            amount_minor=int(row[3]) if isinstance(row[3], int) else 0,
        )
        for row in rows
    ]


def _rollback_sql(loaded: LoadedCase) -> str | None:
    """The declared rollback script, if the case ships one."""
    if loaded.case.candidate.rollback_path is None:
        return None
    return (loaded.benchmark_root / loaded.case.candidate.rollback_path).read_text(encoding="utf-8")


def _credentials_for(
    sandbox: PostgresSandbox,
    world: str,
    targets: list[ProbeTarget],
    app_versions: list[AppVersion],
) -> dict[str, str]:
    """The narrowest credential set the world can work with.

    Never the administrator. The money world needs to read every tenant's rows,
    which the migration role can do through its maintenance policies while
    holding no cluster capability at all.
    """
    roles = {target.probe.role for target in targets}
    if world in {"money", "audit", "rollback", "locks", "interruption"}:
        # These read or write across tenants. The migration role can, through its
        # maintenance policies, while holding no cluster capability at all.
        roles = {MIGRATION_ROLE}
    if world == "rolling":
        roles = {MIGRATION_ROLE, *(s.role for v in app_versions for s in v.statements)}
    return {role: sandbox.credentials.role_passwords[role] for role in sorted(roles)}


def snapshot_disbursements(
    sandbox: PostgresSandbox, database: str
) -> list[DisbursementSnapshotRow]:
    """Capture settled disbursements before the candidate applies."""
    with sandbox.connect(database) as conn:
        rows = conn.execute(
            "SELECT disbursement_id, payment_id, amount_minor FROM disbursements ORDER BY 1"
        ).fetchall()
    return [
        DisbursementSnapshotRow(
            disbursement_id=str(row[0]),
            payment_id=str(row[1]),
            amount_minor=int(row[2]) if isinstance(row[2], int) else 0,
        )
        for row in rows
    ]


def snapshot_audit(sandbox: PostgresSandbox, database: str) -> list[AuditSnapshotRow]:
    """Capture audit history before the candidate applies."""
    with sandbox.connect(database) as conn:
        rows = conn.execute(
            "SELECT event_id, org_id, actor_role, action, entity_id FROM audit_events ORDER BY 1"
        ).fetchall()
    return [
        AuditSnapshotRow(
            event_id=int(row[0]) if isinstance(row[0], int) else 0,
            org_id=str(row[1]),
            actor_role=str(row[2]),
            action=str(row[3]),
            entity_id=str(row[4]),
        )
        for row in rows
    ]


# The lock world measures a statement acquiring its lock, so it needs a database
# the candidate has *not* already been applied to. Every other world measures the
# state the candidate left behind.
CLEAN_DATABASE_WORLDS = frozenset({"locks"})


def run_required_worlds(
    sandbox: PostgresSandbox,
    loaded: LoadedCase,
    *,
    run_id: str,
    trace: TraceWriter | None = None,
    database_by_world: dict[str, str] | None = None,
    compiled_ruling: CompiledRuling | None = None,
    pre_state: list[PaymentSnapshotRow] | None = None,
    pre_audit: list[AuditSnapshotRow] | None = None,
    pre_disbursements: list[DisbursementSnapshotRow] | None = None,
) -> list[WorldResult]:
    """Run every world the case declares required, each on its own database."""
    results: list[WorldResult] = []

    for world in loaded.case.worlds.required:
        name = world.value
        if name in CLEAN_DATABASE_WORLDS:
            database = sandbox.clone(f"{name}-clean")
        else:
            database = (database_by_world or {}).get(name) or prepare_world_database(
                sandbox, loaded, name
            )
        if name == "money" and not (pre_state or []):
            # A money world with no before state cannot attribute a change to
            # the migration, and would report a clean pass for a value it never
            # saw move.
            raise EvidenceIncompleteError(
                "money world requires a pre-migration snapshot",
                detail={"world": name, "case_id": loaded.case.case_id},
            )

        targets = build_targets(sandbox, database, list(loaded.policy.rls_probes))
        request = WorldRequest(
            world=name,
            run_id=run_id,
            host="127.0.0.1",
            port=sandbox.port or 0,
            database=database,
            # Only the roles this world probes. No administrative credential
            # crosses into the child.
            credentials=_credentials_for(sandbox, name, targets, list(loaded.case.app_versions)),
            targets=targets,
            compiled_ruling=compiled_ruling,
            pre_state=pre_state or [],
            pre_audit=pre_audit or [],
            pre_disbursements=pre_disbursements or [],
            app_versions=list(loaded.case.app_versions),
            backfill=loaded.case.backfill,
            lock_probe=loaded.case.lock_probe,
            lock_budget_ms=loaded.policy.lock.budget_ms,
            rollback_sql=_rollback_sql(loaded),
            post_migration_write=loaded.case.post_migration_write,
            deadline_seconds=loaded.case.budgets.world_timeout_seconds,
        )

        if trace is not None:
            trace.emit(
                EventType.CHECK_STARTED,
                actor="world-runner",
                stage=f"world:{name}",
                summary=f"running world {name} on {database}",
                payload={"world": name, "probes": len(targets)},
            )

        result = run_world(request)
        results.append(result)

        if trace is not None:
            trace.emit(
                EventType.CHECK_COMPLETED,
                actor="world-runner",
                stage=f"world:{name}",
                summary=f"world {name} ended as {result.status.value}",
                payload={
                    "world": name,
                    "status": result.status.value,
                    "findings": [finding.invariant_id for finding in result.findings],
                    "semantic_digest": result.semantic_digest,
                },
            )

        sandbox.assert_cluster_unchanged(stage=f"world:{name}")

    return results
