"""Adversarial Test Designer (PRD-FR-011).

Selects from a fixed catalog. The plan schema has no field that can carry a
command, a SQL statement, or a path, so a selection cannot become execution no
matter what the model writes.
"""

from __future__ import annotations

from pathlib import Path

from proofbench.agents.runner import invoke_agent
from proofbench.domain.case import WorldName
from proofbench.domain.contract import MigrationContract, WorldPlan
from proofbench.errors import EvidenceIncompleteError
from proofbench.intake.loader import LoadedCase
from proofbench.providers.base import ModelProvider
from proofbench.tools.router import ToolName, ToolRequest, ToolRouter
from proofbench.tracing.writer import TraceWriter

AGENT = "test_designer"
PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / "test_designer_v1.md"

WORLD_CATALOG = """\
Available worlds. Select only from this list.

- rls           tenant and role isolation: executes the declared role-by-tenant
                access matrix and inspects active policies.
- money         exact minor-unit conversion, value conservation, one settlement
                per payment, and any compiled currency ruling.
- rolling       runs each live application version's declared statements against
                the migrated schema.
- interruption  re-runs the declared backfill, which is what a resumed deploy
                does, and requires the observable state to be unchanged.
- rollback      commits a write after the migration, runs the declared rollback,
                and requires the write to survive.
- locks         compares the relation filenode across the statement; a changed
                filenode means a full table rewrite under ACCESS EXCLUSIVE.
- audit         compares recorded audit events before and after by id and content.

A world only produces evidence if the case declares what it needs: rolling needs
app_versions, interruption needs a backfill, rollback needs a rollback script and
a post-migration write, locks needs a lock probe. Selecting a world the case does
not configure yields an evidence error, not a pass.
"""


def run_test_designer(
    *,
    provider: ModelProvider,
    router: ToolRouter,
    loaded: LoadedCase,
    contract: MigrationContract,
    implemented: frozenset[WorldName],
    trace: TraceWriter | None = None,
) -> WorldPlan:
    """Produce a validated WorldPlan restricted to implemented worlds."""
    catalog = router.call(ToolRequest(actor=AGENT, tool=ToolName.LIST_WORLDS))
    schema = router.call(ToolRequest(actor=AGENT, tool=ToolName.INSPECT_SCHEMA))

    unresolved = [
        assumption
        for assumption in contract.assumptions
        if assumption.safety_relevance.value in {"blocking", "material"}
    ]
    prompt = (
        f"# Case {loaded.case.case_id}: {loaded.case.title}\n\n"
        f"## World catalog\n\n{catalog.output}\n\n"
        f"## Schema\n\n{schema.output}\n\n"
        f"## Contract summary\n\n{contract.summary}\n\n"
        "## Invariants\n\n"
        + "\n".join(f"- {inv.id}: {inv.description}" for inv in contract.invariants)
        + "\n\n## Unresolved safety-relevant assumptions\n\n"
        + ("\n".join(f"- {item.statement}" for item in unresolved) or "- none")
        + f"\n\nSelect the worlds to run for case {loaded.case.case_id}."
    )

    plan = invoke_agent(
        provider=provider,
        model_cls=WorldPlan,
        agent=AGENT,
        prompt_version=PROMPT_VERSION,
        system_prompt=PROMPT_PATH.read_text(encoding="utf-8"),
        user_prompt=prompt,
        max_output_tokens=2000,
        trace=trace,
        seed=loaded.case.seed,
    )

    # Deterministic code compiles the plan before anything runs. A world the
    # agent selected that cannot execute would produce silence, and silence
    # reads as a pass.
    runnable = [entry for entry in plan.entries if entry.world in implemented]
    if not runnable:
        raise EvidenceIncompleteError(
            "world plan selected no implemented world",
            detail={
                "selected": ", ".join(entry.world.value for entry in plan.entries),
                "implemented": ", ".join(sorted(world.value for world in implemented)),
            },
        )
    return plan.model_copy(update={"entries": runnable, "case_id": loaded.case.case_id})
