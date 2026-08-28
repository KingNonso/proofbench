"""Remediation Engineer (PRD-FR-012).

Runs only after a candidate is blocked. It proposes; a clean rerun disposes.

The original candidate is never touched. The correction goes to a separate file
and a fresh database, and the first failure stays in the trace — a bundle that
showed only the corrected run would be describing a migration nobody wrote.
"""

from __future__ import annotations

from pathlib import Path

from proofbench.agents.runner import invoke_agent
from proofbench.config import ORACLE_DIR_NAME
from proofbench.domain.contract import MigrationContract, RemediationPlan
from proofbench.domain.evidence import WorldResult
from proofbench.errors import EvidenceIncompleteError
from proofbench.intake.loader import LoadedCase
from proofbench.providers.base import ModelProvider
from proofbench.tools.router import ToolName, ToolRequest, ToolRouter
from proofbench.tracing.writer import TraceWriter

AGENT = "remediation_engineer"
PROMPT_VERSION = "v1"
PROMPT_PATH = Path(__file__).parent / "prompts" / "remediation_engineer_v1.md"

# Refused outright, whatever the rationale says. An agent that could edit these
# could make any candidate pass without changing the candidate.
FORBIDDEN_TARGETS = (
    ORACLE_DIR_NAME,
    "policy.yaml",
    "trajectory.jsonl",
    "manifest.json",
    "decision.json",
)


def run_remediation_engineer(
    *,
    provider: ModelProvider,
    router: ToolRouter,
    loaded: LoadedCase,
    contract: MigrationContract,
    world_results: list[WorldResult],
    trace: TraceWriter | None = None,
) -> RemediationPlan:
    """Produce a validated correction proposal."""
    failed = [
        finding for result in world_results for finding in result.findings if finding.blocking
    ]
    if not failed:
        raise EvidenceIncompleteError(
            "remediation was invoked with no blocking finding to address",
            detail={"worlds": ", ".join(result.world for result in world_results)},
        )

    candidate = router.call(
        ToolRequest(
            actor=AGENT,
            tool=ToolName.READ_FILE,
            arguments={"path": loaded.case.candidate.migration_path},
        )
    )
    evidence = router.call(
        ToolRequest(actor=AGENT, tool=ToolName.READ_EVIDENCE, arguments={"artifact": "checks.json"})
    )

    prompt = (
        f"# Case {loaded.case.case_id}: {loaded.case.title}\n\n"
        "## Failed invariants\n\n"
        + "\n".join(
            f"- **{finding.invariant_id}**: {finding.summary}\n"
            f"  - expected: {finding.expected}\n"
            f"  - observed: {finding.observed}"
            for finding in failed
        )
        + f"\n\n## Original candidate\n\n```sql\n{candidate.output}\n```\n\n"
        + f"## Executed evidence\n\n```json\n{evidence.output[:6000]}\n```\n\n"
        + f"## Contract\n\n{contract.summary}\n\n"
        + "Propose the smallest correction that addresses the failed invariants "
        "while preserving what the original migration achieved."
    )

    plan = invoke_agent(
        provider=provider,
        model_cls=RemediationPlan,
        agent=AGENT,
        prompt_version=PROMPT_VERSION,
        system_prompt=PROMPT_PATH.read_text(encoding="utf-8"),
        user_prompt=prompt,
        max_output_tokens=4000,
        trace=trace,
        seed=loaded.case.seed,
    )

    _refuse_out_of_bounds(plan)
    expected = {finding.invariant_id for finding in failed}
    if not expected & set(plan.addresses_invariants):
        raise EvidenceIncompleteError(
            "correction does not claim to address any failed invariant",
            detail={
                "failed": ", ".join(sorted(expected)),
                "addressed": ", ".join(plan.addresses_invariants),
            },
        )
    return plan.model_copy(update={"case_id": loaded.case.case_id})


def _refuse_out_of_bounds(plan: RemediationPlan) -> None:
    """Reject a correction that reaches outside the candidate migration."""
    lowered = plan.corrected_sql.lower()
    for target in FORBIDDEN_TARGETS:
        if target in lowered:
            raise EvidenceIncompleteError(
                "correction references material it may not touch",
                detail={"target": target},
            )
    # Restoring row-level security is the point of a correction; disabling it is
    # the defect. A correction that turns the check off is refused.
    for phrase in ("disable row level security", "no force row level security"):
        if phrase in lowered:
            raise EvidenceIncompleteError(
                "correction weakens the control it was asked to restore",
                detail={"phrase": phrase},
            )
