"""Contract Analyst (PRD-FR-010).

Read-only. It separates what the evidence supports from what it does not, and it
has no field in which to express an opinion about safety. That is the boundary:
the agent contributes structure, the deterministic checks contribute verdicts.
"""

from __future__ import annotations

from pathlib import Path

from proofbench.agents.runner import invoke_agent
from proofbench.domain.contract import MigrationContract
from proofbench.intake.loader import LoadedCase
from proofbench.providers.base import ModelProvider
from proofbench.tools.router import ToolName, ToolRequest, ToolRouter
from proofbench.tracing.writer import TraceWriter

AGENT = "contract_analyst"
PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / "contract_analyst_v1.md"


def gather_context(router: ToolRouter, loaded: LoadedCase) -> str:
    """Collect what the agent is allowed to see, through the router."""
    parts: list[str] = []

    for label, request in (
        (
            "candidate migration",
            ToolRequest(
                actor=AGENT,
                tool=ToolName.READ_FILE,
                arguments={"path": loaded.case.candidate.migration_path},
            ),
        ),
        (
            "policy",
            ToolRequest(
                actor=AGENT,
                tool=ToolName.READ_FILE,
                arguments={"path": loaded.case.policy_path},
            ),
        ),
        ("schema", ToolRequest(actor=AGENT, tool=ToolName.INSPECT_SCHEMA)),
        ("declared roles", ToolRequest(actor=AGENT, tool=ToolName.INSPECT_ROLES)),
    ):
        result = router.call(request)
        # A refusal is recorded verbatim rather than dropped: an agent that
        # cannot tell "denied" from "empty" will build a contract on an absence
        # it never knew about.
        body = result.output if result.allowed else f"DENIED: {result.denial_reason}"
        parts.append(f"## {label}\n\n{body}")

    for index, relative in enumerate(loaded.case.visible_tests):
        result = router.call(
            ToolRequest(actor=AGENT, tool=ToolName.READ_FILE, arguments={"path": relative})
        )
        body = result.output if result.allowed else f"DENIED: {result.denial_reason}"
        parts.append(f"## visible test {index}\n\n{body}")

    return "\n\n".join(parts)


def build_prompt(loaded: LoadedCase, context: str) -> str:
    return (
        f"# Case {loaded.case.case_id}: {loaded.case.title}\n\n"
        f"{loaded.case.description}\n\n"
        f"{context}\n\n"
        f"Produce the MigrationContract for case {loaded.case.case_id}."
    )


def run_contract_analyst(
    *,
    provider: ModelProvider,
    router: ToolRouter,
    loaded: LoadedCase,
    trace: TraceWriter | None = None,
) -> MigrationContract:
    """Produce a validated MigrationContract, or fail the stage."""
    context = gather_context(router, loaded)
    contract = invoke_agent(
        provider=provider,
        model_cls=MigrationContract,
        agent=AGENT,
        prompt_version=PROMPT_VERSION,
        system_prompt=PROMPT_PATH.read_text(encoding="utf-8"),
        user_prompt=build_prompt(loaded, context),
        max_output_tokens=4000,
        trace=trace,
        seed=loaded.case.seed,
    )
    if contract.case_id != loaded.case.case_id:
        contract = contract.model_copy(update={"case_id": loaded.case.case_id})
    return contract
