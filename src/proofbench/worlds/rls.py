"""Tenant and role isolation world (PRD-FR-031).

Executes the policy's probes as the real roles and compares what happened with
what the policy declared. Three rules shape the code:

**Both directions are probed.** A world that only checked that permitted access
still works would pass a migration that granted the world to everyone.

**Denial and error are different observable facts.** Row-level security denies by
filtering to zero rows; a missing grant raises 42501. Collapsing them would make
a dropped policy indistinguishable from an intact one.

**An unexpected outcome is an evidence error, not a denial.** A probe that hit an
undefined table, or a ``deny_empty`` probe with no rows on the other side to
withhold, proves nothing. Reporting either as a clean pass is how a broken world
quietly certifies an unsafe migration.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import psycopg
from psycopg import sql

from proofbench.domain.case import Operation, ProbeOutcome, RlsProbeSpec
from proofbench.domain.evidence import (
    AccessObservation,
    CheckResult,
    CheckStatus,
    EvidenceFailure,
    Finding,
    WorldResult,
    WorldStatus,
)
from proofbench.worlds.base import ProbeTarget, World, WorldRequest

# The only SQLSTATE that means "this role is not allowed to do that".
# Anything else during a probe is an evidence error: the probe did not measure
# what it claimed to measure.
INSUFFICIENT_PRIVILEGE = "42501"

WORLD_NAME = "rls"


class RlsWorld(World):
    """Role-by-tenant access matrix over the declared probes."""

    name = WORLD_NAME
    threatened_invariants = ("INV-RLS-001", "INV-RLS-002", "INV-RLS-003")

    def run(self, request: WorldRequest) -> WorldResult:
        started = datetime.now(UTC)
        clock = time.monotonic()

        checks: list[CheckResult] = []
        observations: list[AccessObservation] = []
        failures: list[EvidenceFailure] = []

        for target in request.targets:
            check, observation, failure = self._probe(request, target)
            checks.append(check)
            if observation is not None:
                observations.append(observation)
            if failure is not None:
                failures.append(failure)

        findings = _findings(request.targets, observations)
        ended = datetime.now(UTC)

        if failures:
            status = WorldStatus.ERROR
        elif findings:
            status = WorldStatus.FAILED
        else:
            status = WorldStatus.PASSED

        return WorldResult(
            world=self.name,
            status=status,
            threatened_invariants=list(self.threatened_invariants),
            checks=checks,
            findings=findings,
            observations=observations,
            failures=failures,
            started_at=started,
            ended_at=ended,
            duration_ms=int((time.monotonic() - clock) * 1000),
        ).with_digest()

    def _probe(
        self, request: WorldRequest, target: ProbeTarget
    ) -> tuple[CheckResult, AccessObservation | None, EvidenceFailure | None]:
        probe = target.probe
        check_id = f"rls:{probe.probe_id}"
        statement = _build_statement(probe)
        command = statement.as_string(None) if hasattr(statement, "as_string") else str(statement)
        clock = time.monotonic()

        # A probe whose target set is empty cannot distinguish a boundary that
        # held from a table that had nothing to withhold.
        if probe.expected_outcome is not ProbeOutcome.DENY_ERROR and target.target_row_count == 0:
            return (
                CheckResult(
                    check_id=check_id,
                    command=command,
                    status=CheckStatus.ERROR,
                    duration_ms=0,
                    detail="no target rows exist; the probe cannot observe anything",
                ),
                None,
                EvidenceFailure(
                    stage=f"world:{WORLD_NAME}",
                    reason=f"probe {probe.probe_id} has no target rows to observe",
                    causes=[f"expected outcome {probe.expected_outcome.value} is vacuous"],
                ),
            )

        rows: list[tuple[object, ...]] = []
        sqlstate: str | None = None
        error_text: str | None = None

        try:
            with psycopg.connect(request.dsn(probe.role)) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        sql.SQL("SET LOCAL aidledger.org_id = {}").format(
                            sql.Literal(str(probe.session_tenant))
                        )
                    )
                    cur.execute(statement, probe.values)
                    if cur.description is not None:
                        rows = cur.fetchall()
                # Every probe rolls back. A world must not leave the database it
                # measured in a different state than it found it.
                conn.rollback()
        except psycopg.Error as exc:
            sqlstate = exc.sqlstate
            error_text = str(exc)[:300]

        duration_ms = int((time.monotonic() - clock) * 1000)
        observed = _classify(sqlstate, len(rows))

        if observed is None:
            return (
                CheckResult(
                    check_id=check_id,
                    command=command,
                    status=CheckStatus.ERROR,
                    duration_ms=duration_ms,
                    sqlstate=sqlstate,
                    detail=error_text,
                ),
                None,
                EvidenceFailure(
                    stage=f"world:{WORLD_NAME}",
                    reason=f"probe {probe.probe_id} failed with an unexpected SQLSTATE",
                    causes=[f"sqlstate={sqlstate}", error_text or ""],
                ),
            )

        matched = observed is probe.expected_outcome and _rows_as_expected(probe, len(rows))
        if (
            matched
            and probe.expected_outcome is ProbeOutcome.DENY_ERROR
            and sqlstate != probe.expected_sqlstate
        ):
            matched = False

        observation = AccessObservation(
            probe_id=probe.probe_id,
            role=probe.role,
            table=probe.table,
            operation=probe.operation.value,
            scope=probe.scope.value,
            session_tenant=str(probe.session_tenant),
            target_tenant=str(probe.target_tenant),
            permitted_by_policy=probe.expected_outcome is ProbeOutcome.ALLOW,
            observed_allowed=observed is ProbeOutcome.ALLOW,
            rows_seen=len(rows),
            row_keys=[_row_key(row) for row in rows],
            sqlstate=sqlstate,
        )

        return (
            CheckResult(
                check_id=check_id,
                command=command,
                status=CheckStatus.PASSED if matched else CheckStatus.FAILED,
                duration_ms=duration_ms,
                sqlstate=sqlstate,
                blocking_class=probe.invariant_id,
                detail=None
                if matched
                else f"expected {probe.expected_outcome.value}, "
                f"observed {observed.value} with {len(rows)} row(s)",
            ),
            observation,
            None,
        )


def _build_statement(probe: RlsProbeSpec) -> sql.Composed:
    """Build the parameterized probe statement.

    Identifiers were validated as data at the schema boundary and are composed
    with ``sql.Identifier`` here; values are always bound, never interpolated.
    """
    table = sql.Identifier(probe.table)
    columns = sql.SQL(", ").join(sql.Identifier(name) for name in probe.evidence_columns)
    predicate = sql.SQL(probe.predicate)  # noqa: S608 - policy-authored, validated fragment

    if probe.operation is Operation.SELECT:
        return sql.SQL("SELECT {cols} FROM {table} WHERE {pred}").format(
            cols=columns, table=table, pred=predicate
        )
    if probe.operation is Operation.UPDATE:
        # A no-op assignment still evaluates the USING and WITH CHECK clauses,
        # and the transaction rolls back regardless.
        return sql.SQL("UPDATE {table} SET org_id = org_id WHERE {pred} RETURNING {cols}").format(
            table=table, pred=predicate, cols=columns
        )
    if probe.operation is Operation.DELETE:
        return sql.SQL("DELETE FROM {table} WHERE {pred} RETURNING {cols}").format(
            table=table, pred=predicate, cols=columns
        )
    # INSERT probes test the grant, not the data: selecting no rows means a
    # permitted role returns zero rows while an unprivileged one raises 42501.
    # (Not usable against a table with a GENERATED ALWAYS identity column.)
    return sql.SQL("INSERT INTO {table} SELECT * FROM {table} WHERE false RETURNING {cols}").format(
        table=table, cols=columns
    )


def _classify(sqlstate: str | None, row_count: int) -> ProbeOutcome | None:
    """Map a raw outcome to a policy category, or None if it measured nothing."""
    if sqlstate == INSUFFICIENT_PRIVILEGE:
        return ProbeOutcome.DENY_ERROR
    if sqlstate is not None:
        return None
    return ProbeOutcome.ALLOW if row_count > 0 else ProbeOutcome.DENY_EMPTY


def _rows_as_expected(probe: RlsProbeSpec, row_count: int) -> bool:
    if probe.expected_row_count is None:
        return True
    return probe.expected_row_count == row_count


def _row_key(row: tuple[object, ...]) -> str:
    return "|".join("" if value is None else str(value) for value in row)


def _findings(targets: list[ProbeTarget], observations: list[AccessObservation]) -> list[Finding]:
    """Group mismatched observations into one finding per invariant."""
    expected_by_probe = {target.probe.probe_id: target.probe for target in targets}
    grouped: dict[str, list[AccessObservation]] = {}

    for observation in observations:
        probe = expected_by_probe[observation.probe_id]
        actual = ProbeOutcome.ALLOW if observation.observed_allowed else None
        if actual is None:
            actual = (
                ProbeOutcome.DENY_ERROR
                if observation.sqlstate == INSUFFICIENT_PRIVILEGE
                else ProbeOutcome.DENY_EMPTY
            )
        mismatch = actual is not probe.expected_outcome or not _rows_as_expected(
            probe, observation.rows_seen
        )
        if mismatch:
            grouped.setdefault(probe.invariant_id, []).append(observation)

    findings: list[Finding] = []
    for invariant_id, items in sorted(grouped.items()):
        probes = [expected_by_probe[item.probe_id] for item in items]
        findings.append(
            Finding(
                invariant_id=invariant_id,
                blocking=True,
                summary=_summarise(invariant_id, items),
                expected="; ".join(f"{p.probe_id}: {p.expected_outcome.value}" for p in probes),
                observed="; ".join(
                    f"{item.probe_id}: {item.rows_seen} row(s)"
                    + (f", sqlstate {item.sqlstate}" if item.sqlstate else "")
                    for item in items
                ),
                check_ids=[f"rls:{item.probe_id}" for item in items],
                observations=items,
            )
        )
    return findings


def _summarise(invariant_id: str, items: list[AccessObservation]) -> str:
    leaked = [item for item in items if item.observed_allowed and not item.permitted_by_policy]
    if leaked:
        first = leaked[0]
        tenants = sorted({item.target_tenant for item in leaked})
        return (
            f"{first.role} reached {first.rows_seen} {first.table} row(s) belonging to "
            f"organisation {first.target_tenant}"
            + (f" and {len(tenants) - 1} other tenant(s)" if len(tenants) > 1 else "")
        )
    lost = [item for item in items if not item.observed_allowed and item.permitted_by_policy]
    if lost:
        first = lost[0]
        return f"{first.role} lost required {first.operation} access to {first.table}"
    return f"{invariant_id} did not hold for {len(items)} probe(s)"
