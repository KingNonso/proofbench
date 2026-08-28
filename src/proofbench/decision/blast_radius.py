"""Blast radius derived from executed evidence only.

``confirmed`` may contain nothing that was not observed. An impact inferred from
reading a migration but never executed belongs in ``possible``, and the two are
never merged (PRD-FR-041): a reviewer needs to know which of these actually
happened in a sandbox.

``possible`` is empty in this slice, honestly so — it comes from contract
analysis, and no agent exists yet.
"""

from __future__ import annotations

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
