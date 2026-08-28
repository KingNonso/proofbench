"""Money and reconciliation world (PRD-FR-032), currency scope.

Executes the constraint a human ruling compiled to, and checks that the
migration honoured its own scope. Three questions, all answerable only by
comparing before with after:

1. Did every row the ruling covers get the ruled value?
2. Did any row *outside* the ruling get its currency changed anyway?
3. Did any amount move?

Reads as the migration role, not as an administrator. That role holds the
maintenance policies it needs to see every tenant's rows, and no cluster
capability at all -- so a reconciliation check never requires a credential the
child was deliberately not given.

The third question is the one that catches the quiet disaster. A currency backfill has no
business touching ``amount_minor``, and a comparison in integer minor units says
so exactly — there is no float anywhere in this path, so "close enough" is not a
result this world can produce.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime

import psycopg

from proofbench.domain.evidence import (
    CheckResult,
    CheckStatus,
    EvidenceFailure,
    Finding,
    WorldResult,
    WorldStatus,
)
from proofbench.sandbox.postgres import MIGRATION_ROLE
from proofbench.worlds.base import PaymentSnapshotRow, World, WorldRequest

WORLD_NAME = "money"
CONSERVATION_INVARIANT = "INV-MONEY-001"


class MoneyWorld(World):
    """Verifies a compiled currency ruling and value conservation."""

    name = WORLD_NAME
    threatened_invariants = (CONSERVATION_INVARIANT, "INV-MONEY-002")

    def run(self, request: WorldRequest) -> WorldResult:
        started = datetime.now(UTC)
        clock = time.monotonic()

        checks: list[CheckResult] = []
        findings: list[Finding] = []
        failures: list[EvidenceFailure] = []

        if not request.pre_state:
            failures.append(
                EvidenceFailure(
                    stage=f"world:{WORLD_NAME}",
                    reason="no pre-migration snapshot; nothing can be compared",
                )
            )
            return self._result(request, started, clock, checks, findings, failures)

        try:
            with psycopg.connect(request.dsn(MIGRATION_ROLE)) as conn:
                after: dict[str, tuple[str | None, int]] = {
                    str(row[0]): (
                        None if row[1] is None else str(row[1]).strip(),
                        int(row[2]),
                    )
                    for row in conn.execute(
                        "SELECT payment_id, currency_code, amount_minor FROM payments"
                    ).fetchall()
                }
        except psycopg.Error as exc:
            failures.append(
                EvidenceFailure(
                    stage=f"world:{WORLD_NAME}",
                    reason="could not read the post-migration state",
                    causes=[f"sqlstate={exc.sqlstate}", str(exc)[:200]],
                )
            )
            return self._result(request, started, clock, checks, findings, failures)

        before = {row.payment_id: row for row in request.pre_state}

        checks.append(self._conservation(before, after, findings, clock))
        if request.compiled_ruling is not None:
            checks.extend(self._ruling_checks(request, before, after, findings, clock))

        return self._result(request, started, clock, checks, findings, failures)

    def _conservation(
        self,
        before: dict[str, PaymentSnapshotRow],
        after: dict[str, tuple[str | None, int]],
        findings: list[Finding],
        clock: float,
    ) -> CheckResult:
        moved = [
            payment_id
            for payment_id, row in before.items()
            if payment_id in after and after[payment_id][1] != row.amount_minor
        ]
        if moved:
            findings.append(
                Finding(
                    invariant_id=CONSERVATION_INVARIANT,
                    blocking=True,
                    summary=f"{len(moved)} payment amount(s) changed during the migration",
                    expected="every amount_minor unchanged",
                    observed=f"changed: {', '.join(sorted(moved)[:5])}",
                    check_ids=["money:conservation"],
                )
            )
        return CheckResult(
            check_id="money:conservation",
            command="compare amount_minor before and after, in integer minor units",
            status=CheckStatus.FAILED if moved else CheckStatus.PASSED,
            duration_ms=int((time.monotonic() - clock) * 1000),
            blocking_class=CONSERVATION_INVARIANT,
        )

    def _ruling_checks(
        self,
        request: WorldRequest,
        before: dict[str, PaymentSnapshotRow],
        after: dict[str, tuple[str | None, int]],
        findings: list[Finding],
        clock: float,
    ) -> list[CheckResult]:
        ruling = request.compiled_ruling
        assert ruling is not None  # noqa: S101 - guarded by the caller

        in_scope = {payment_id for payment_id, row in before.items() if row.currency_code is None}

        # 1. Rows the ruling covers must carry the ruled value.
        wrong = sorted(
            payment_id
            for payment_id in in_scope
            if payment_id in after and after[payment_id][0] != ruling.expected_value
        )
        # 2. Rows the ruling does not cover must be untouched.
        outside = sorted(
            payment_id
            for payment_id, row in before.items()
            if payment_id not in in_scope
            and payment_id in after
            and after[payment_id][0] != row.currency_code
        )

        if wrong:
            findings.append(
                Finding(
                    invariant_id=ruling.invariant_id,
                    blocking=True,
                    summary=(
                        f"{len(wrong)} row(s) in the ruling's scope do not carry "
                        f"{ruling.expected_value!r}"
                    ),
                    expected=ruling.description,
                    observed=f"not set as ruled: {', '.join(wrong[:5])}",
                    check_ids=["money:ruling-scope"],
                )
            )
        if outside:
            findings.append(
                Finding(
                    invariant_id=ruling.invariant_id,
                    blocking=True,
                    summary=(
                        f"the migration changed the currency of {len(outside)} row(s) "
                        "the ruling does not cover"
                    ),
                    expected="rows outside the ruling's scope are untouched",
                    observed=f"changed: {', '.join(outside[:5])}",
                    check_ids=["money:ruling-overreach"],
                )
            )

        duration = int((time.monotonic() - clock) * 1000)
        return [
            CheckResult(
                check_id="money:ruling-scope",
                command=ruling.description,
                status=CheckStatus.FAILED if wrong else CheckStatus.PASSED,
                duration_ms=duration,
                blocking_class=ruling.invariant_id,
            ),
            CheckResult(
                check_id="money:ruling-overreach",
                command="confirm rows outside the ruling's scope kept their currency",
                status=CheckStatus.FAILED if outside else CheckStatus.PASSED,
                duration_ms=duration,
                blocking_class=ruling.invariant_id,
            ),
        ]

    def _result(
        self,
        request: WorldRequest,
        started: datetime,
        clock: float,
        checks: list[CheckResult],
        findings: list[Finding],
        failures: list[EvidenceFailure],
    ) -> WorldResult:
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
            failures=failures,
            started_at=started,
            ended_at=datetime.now(UTC),
            duration_ms=int((time.monotonic() - clock) * 1000),
        ).with_digest()
