"""The deterministic decision policy.

A pure function over typed evidence. Agent text is never an input, so no amount
of confident prose can turn a failed blocking check into a pass (PRD-FR-040).

Precedence is ordered, and the order is the point:

1. an evidence failure, world error, or timeout  -> EVIDENCE_INCOMPLETE
2. a confirmed blocking finding                  -> BLOCKED
3. an unresolved material authority question     -> DOMAIN_RULING_REQUIRED
4. no world ran at all, and none was deferred    -> EVIDENCE_INCOMPLETE
5. otherwise                                     -> READY_FOR_REVIEW

Evidence completeness outranks a blocking failure deliberately. If a run could
not produce trustworthy evidence, its blocking findings are not trustworthy
either, and reporting BLOCKED would claim more than the run knows.
"""

from __future__ import annotations

from collections.abc import Sequence

from proofbench.decision.blast_radius import confirmed_from, possible_from
from proofbench.domain.contract import MigrationContract
from proofbench.domain.decision import BlastRadiusItem, DecisionRecord, ExternalState
from proofbench.domain.evidence import EvidenceFailure, WorldResult, WorldStatus

POLICY_VERSION = 1

_INCOMPLETE_STATUSES = frozenset({WorldStatus.ERROR, WorldStatus.TIMEOUT})

REQUIRED_ACTIONS = {
    ExternalState.READY_FOR_REVIEW: (
        "A qualified engineer reviews the certificate and the candidate migration. "
        "This is not an automatic approval."
    ),
    ExternalState.BLOCKED: "Correct the candidate migration and re-run.",
    ExternalState.DOMAIN_RULING_REQUIRED: (
        "A qualified domain owner records a scoped ruling on the open question."
    ),
    ExternalState.EVIDENCE_INCOMPLETE: (
        "Fix the evidence failure and re-run. This result is not a pass."
    ),
}


def decide(
    world_results: Sequence[WorldResult],
    authority_questions: Sequence[str] = (),
    evidence_failures: Sequence[EvidenceFailure] = (),
    *,
    contract: MigrationContract | None = None,
) -> DecisionRecord:
    """Map typed evidence to exactly one external state.

    The contract contributes hypotheses to ``possible`` and nothing else: it is
    typed agent output, and letting it move the external state would make the
    deterministic policy advisory (PRD-FR-040). Every branch below chooses its
    state before ``possible`` is even attached.
    """
    reasons: list[str] = []
    decisive: list[str] = []
    possible = possible_from(contract, list(world_results))

    incomplete = [result for result in world_results if result.status in _INCOMPLETE_STATUSES]
    world_failures = [failure for result in world_results for failure in result.failures]
    all_failures = [*evidence_failures, *world_failures]

    if incomplete or all_failures:
        for result in incomplete:
            reasons.append(f"world {result.world} ended as {result.status.value}")
            decisive.extend(
                check.check_id for check in result.checks if check.status.value != "passed"
            )
        for failure in all_failures:
            reasons.append(f"{failure.stage}: {failure.reason}")
            reasons.extend(failure.causes)
        return _record(
            ExternalState.EVIDENCE_INCOMPLETE,
            reasons,
            decisive,
            [],
            possible=possible,
            evidence_complete=False,
        )

    blocking = [
        (result, finding)
        for result in world_results
        for finding in result.findings
        if finding.blocking
    ]
    if blocking:
        for result, finding in blocking:
            reasons.append(
                f"{finding.invariant_id} failed in world {result.world}: {finding.summary}"
            )
            decisive.extend(finding.check_ids)
        return _record(
            ExternalState.BLOCKED,
            reasons,
            decisive,
            confirmed_from(list(world_results)),
            possible=possible,
            evidence_complete=True,
        )

    if authority_questions:
        # Worlds deferred pending a ruling are not missing evidence. Deferring
        # them is the correct behaviour: running a world whose invariant the open
        # question governs would measure an assumption and report it as a fact.
        reasons.extend(
            f"unresolved authority question: {question}" for question in authority_questions
        )
        return _record(
            ExternalState.DOMAIN_RULING_REQUIRED,
            reasons,
            decisive,
            [],
            possible=possible,
            evidence_complete=True,
        )

    if not world_results:
        # Nothing ran and nobody asked for a ruling, so nothing is known.
        reasons.append("no world produced a result")
        return _record(
            ExternalState.EVIDENCE_INCOMPLETE,
            reasons,
            decisive,
            [],
            possible=possible,
            evidence_complete=False,
        )

    reasons.extend(f"world {result.world} passed" for result in world_results)
    decisive.extend(check.check_id for result in world_results for check in result.checks)
    return _record(
        ExternalState.READY_FOR_REVIEW,
        reasons,
        decisive,
        [],
        possible=possible,
        evidence_complete=True,
    )


def _record(
    state: ExternalState,
    reasons: list[str],
    decisive: list[str],
    confirmed: list[BlastRadiusItem],
    *,
    possible: list[BlastRadiusItem],
    evidence_complete: bool,
) -> DecisionRecord:
    return DecisionRecord(
        external_state=state,
        policy_version=POLICY_VERSION,
        reasons=reasons,
        decisive_check_ids=sorted(set(decisive)),
        confirmed=confirmed,
        possible=possible,
        required_action=REQUIRED_ACTIONS[state],
        evidence_complete=evidence_complete,
    )
