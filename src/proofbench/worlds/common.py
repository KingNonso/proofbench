"""Shared shape for the worlds that compare a before state with an after state.

Most deployment failures are invisible in a final schema and obvious in a
difference: a row that moved, a row that vanished, a value that changed when
nothing should have touched it. These helpers keep that comparison identical
across worlds so the evidence reads the same wherever it came from.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

from proofbench.domain.evidence import (
    CheckResult,
    CheckStatus,
    EvidenceFailure,
    Finding,
    WorldResult,
    WorldStatus,
)


def check(
    check_id: str,
    command: str,
    *,
    failed: bool,
    clock: float,
    invariant: str,
    sqlstate: str | None = None,
    detail: str | None = None,
) -> CheckResult:
    """One executed comparison."""
    return CheckResult(
        check_id=check_id,
        command=command,
        status=CheckStatus.FAILED if failed else CheckStatus.PASSED,
        duration_ms=int((time.monotonic() - clock) * 1000),
        sqlstate=sqlstate,
        blocking_class=invariant,
        detail=detail,
    )


def finish(
    world: str,
    threatened: tuple[str, ...],
    started: datetime,
    clock: float,
    checks: list[CheckResult],
    findings: list[Finding],
    failures: list[EvidenceFailure],
) -> WorldResult:
    """Assemble the result, deriving status from evidence rather than intent."""
    if failures:
        status = WorldStatus.ERROR
    elif findings:
        status = WorldStatus.FAILED
    else:
        status = WorldStatus.PASSED
    return WorldResult(
        world=world,
        status=status,
        threatened_invariants=list(threatened),
        checks=checks,
        findings=findings,
        failures=failures,
        started_at=started,
        ended_at=datetime.now(UTC),
        duration_ms=int((time.monotonic() - clock) * 1000),
    ).with_digest()


def missing_configuration(world: str, what: str) -> EvidenceFailure:
    """A world with no configuration refuses rather than inventing a default.

    A default here would silently test something the case never declared, and
    report the result as though the case had asked for it.
    """
    return EvidenceFailure(
        stage=f"world:{world}",
        reason=f"{world} world requires {what}, which this case does not declare",
    )
