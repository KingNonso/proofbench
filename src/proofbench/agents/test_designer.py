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
                access matrix and inspects active policies. Implemented.
- money         exact minor-unit conversion, conservation, idempotency. Implemented
                for currency-evidence checks.
- rolling       interleaves old and new application versions across stages. Not yet
                implemented; selecting it will produce no evidence.
- interruption  fails a backfill at a checkpoint and resumes. Not yet implemented.
- rollback      writes after migration start, then rolls back. Not yet implemented.
- locks         measures blocking operations against the lock budget. Not yet implemented.
- audit         proves audit history remains append-only and attributable. Not yet
                implemented.
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
