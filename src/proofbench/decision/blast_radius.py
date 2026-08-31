"""Blast radius derived from executed evidence, and hypotheses that were not.

``confirmed`` may contain nothing that was not observed. An impact inferred from
reading a migration but never executed belongs in ``possible``, and the two are
never merged (PRD-FR-041): a reviewer needs to know which of these actually
happened in a sandbox.

``possible`` comes from the Migration Contract: an invariant the analyst
declared safety-relevant that no executed world settled is precisely the
hypothesis a reviewer is otherwise asked to carry in their head. Its empty
``check_ids`` list is the label — a possible impact is a hypothesis that was
not executed (PRD §16) — and nothing in it ever influences the external state.
"""

from __future__ import annotations

from proofbench.domain.contract import Materiality, MigrationContract
from proofbench.domain.decision import BlastRadiusItem
from proofbench.domain.evidence import WorldResult


def confirmed_from(world_results: list[WorldResult]) -> list[BlastRadiusItem]:
    """Derive confirmed impacts from findings that carry executed observations."""
    items: list[BlastRadiusItem] = []

    for result in world_results:
        for finding in result.findings:
            if not finding.blocking:
                continue
            for observation in finding.observations:
                # Only an observation that saw access it should not have had is
                # an impact. A denial that behaved correctly is evidence, not harm.
                if observation.observed_allowed and not observation.permitted_by_policy:
                    items.append(
                        BlastRadiusItem(
                            invariant_id=finding.invariant_id,
                            role=observation.role,
                            operation=observation.operation,
                            affected_tenant=observation.target_tenant,
                            rows_affected=observation.rows_seen,
                            row_keys=sorted(observation.row_keys),
                            # The check that produced *this* observation, not
                            # every check in the finding. A confirmed impact
                            # citing four checks when one saw it is not
                            # traceable evidence, it is a bibliography.
                            check_ids=[f"{result.world}:{observation.probe_id}"],
                            summary=(
                                f"{observation.role} reached {observation.rows_seen} "
                                f"{observation.table} row(s) belonging to organisation "
                                f"{observation.target_tenant} via {observation.operation}"
                            ),
                        )
                    )

    return items


def possible_from(
    contract: MigrationContract | None, world_results: list[WorldResult]
) -> list[BlastRadiusItem]:
    """Hypothetical impacts: declared by the contract, settled by nothing that ran.

    An invariant is settled when an executed world either named it as threatened
    coverage or produced a finding against it. What remains — blocking or
    material only; a minor invariant left unexecuted is a footnote, not a
    hypothesis worth a reviewer's attention — becomes a ``possible`` entry
    linked to the contract by its invariant id. ``rows_affected`` is zero and
    ``check_ids`` is empty because nothing was executed, which is the claim.
    """
    if contract is None:
        return []

    settled = {invariant for result in world_results for invariant in result.threatened_invariants}
    settled.update(finding.invariant_id for result in world_results for finding in result.findings)

    return [
        BlastRadiusItem(
            invariant_id=invariant.id,
            role="unverified",
            operation=invariant.executable_check,
            affected_tenant="unknown",
            rows_affected=0,
            check_ids=[],
            summary=(
                f"{invariant.blocking_class.value} invariant declared in the contract but "
                f"settled by no executed check in this run: {invariant.description}"
            ),
        )
        for invariant in contract.invariants
        if invariant.id not in settled and invariant.blocking_class is not Materiality.MINOR
    ]
