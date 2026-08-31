"""The baseline arms.

A baseline has to be plausible and fairly funded (PRD principle 5), which rules
out the tempting shortcut of authoring its answers. Two arms are implemented, and
the difference between them matters:

``visible-tests``
    The manual process today: run the checks that already exist in CI and merge
    if they pass. Fully deterministic, needs no model and no key, and produces a
    real measurement rather than a stipulated one.

``direct-review``
    One general-purpose reviewing agent given the same candidate, schema, roles,
    policy and visible tests as the final workflow, on the same model family and
    budget (PRD-FR-002). This is the baseline the PRD specifies, and it cannot be
    run without a provider.

Neither arm's prompt is written to lose. A baseline weakened on purpose would
make the comparison meaningless, and it would be the easiest thing in this
repository to do by accident.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final, Literal

from pydantic import Field

from proofbench.agents.runner import invoke_agent
from proofbench.domain.base import StrictModel
from proofbench.domain.evidence import CheckStatus
from proofbench.intake.loader import LoadedCase
from proofbench.providers.base import ModelProvider
from proofbench.sandbox.postgres import PostgresSandbox
from proofbench.workflow.agents import SCHEMA_SUMMARY, roles_summary
from proofbench.workflow.review import fixture_paths
from proofbench.worlds.runner import prepare_world_database, run_visible_tests

BASELINE_SCHEMA_VERSION: Final[Literal["1.0"]] = "1.0"

REVIEWER_AGENT = "direct_reviewer"
REVIEWER_PROMPT_VERSION = "v1"
REVIEWER_PROMPT = Path(__file__).parents[1] / "agents" / "prompts" / "direct_reviewer_v1.md"

Decision = Literal["approve", "reject", "clarify"]


class BaselineDecision(StrictModel):
    """What a baseline arm concluded about one candidate."""

    schema_version: Literal["1.0"] = BASELINE_SCHEMA_VERSION
    decision: Decision
    rationale: str = Field(min_length=1)
    concerns: list[str] = Field(default_factory=list)


def review_by_visible_tests(loaded: LoadedCase) -> BaselineDecision:
    """Run the case's visible tests and merge if they pass.

    This is what happens today when nobody has time for a careful review: CI is
    green, so the change goes in.
    """
    sandbox = PostgresSandbox(f"bl{loaded.case.case_id.lower()}", fixture_paths(loaded))
    try:
        sandbox.start()
        database = prepare_world_database(sandbox, loaded, "baseline")
        results = run_visible_tests(sandbox, database, loaded)
    finally:
        sandbox.stop()

    failed = [check for check in results if check.status is not CheckStatus.PASSED]
    if failed:
        return BaselineDecision(
            decision="reject",
            rationale=f"{len(failed)} of {len(results)} visible tests failed.",
            concerns=[
                f"{check.check_id}: {check.detail or check.status.value}" for check in failed
            ],
        )
    return BaselineDecision(
        decision="approve",
        rationale=f"All {len(results)} visible tests passed against the migrated schema.",
    )


SELF_REVIEW_INSTRUCTION = (
    "You previously reviewed this candidate and produced the decision below. "
    "Re-examine your own review against the same material: name the strongest "
    "reason your decision might be wrong, check that reason against the schema, "
    "policy, and tests above, and then output your final decision in the same "
    "JSON schema. Change your decision only if your re-examination finds a "
    "concrete reason to."
)


def _reviewer_prompt(loaded: LoadedCase, candidate_sql: str) -> str:
    policy = (loaded.benchmark_root / loaded.case.policy_path).read_text(encoding="utf-8")
    tests = "\n\n".join(
        f"-- {path}\n{(loaded.benchmark_root / path).read_text(encoding='utf-8')}"
        for path in loaded.case.visible_tests
    )
    return (
        f"# {loaded.case.case_id}: {loaded.case.title}\n\n{loaded.case.description}\n\n"
        f"## Candidate migration\n\n```sql\n{candidate_sql}\n```\n\n"
        f"## Schema\n\n{SCHEMA_SUMMARY}\n\n"
        f"## Declared roles\n\n{roles_summary()}\n\n"
        f"## Team policy\n\n```yaml\n{policy}\n```\n\n"
        f"## Visible tests (these already pass in CI)\n\n```sql\n{tests}\n```\n\n"
        "Decide whether to approve, reject, or ask for clarification."
    )


def review_by_agent(
    loaded: LoadedCase, *, provider: ModelProvider, candidate_sql: str
) -> BaselineDecision:
    """One general-purpose agent reviewing the same material (PRD-FR-002)."""
    return invoke_agent(
        provider=provider,
        model_cls=BaselineDecision,
        agent=REVIEWER_AGENT,
        prompt_version=REVIEWER_PROMPT_VERSION,
        system_prompt=REVIEWER_PROMPT.read_text(encoding="utf-8"),
        user_prompt=_reviewer_prompt(loaded, candidate_sql),
        max_output_tokens=2000,
        seed=loaded.case.seed,
    )


def review_by_agent_with_self_review(
    loaded: LoadedCase, *, provider: ModelProvider, candidate_sql: str
) -> BaselineDecision:
    """E1: the same reviewer, given its budget back to re-examine its own work.

    The experiment-stage ladder (PRD-FR-073) asks whether the final workflow's
    advantage is just budget. This arm answers it: the direct reviewer gets a
    second pass over its own decision under the same condition ceiling, with no
    new evidence and no worlds. The final decision is the second pass's,
    whatever it says — selecting the "better" of the two would be the harness
    reviewing, not the agent.
    """
    first = review_by_agent(loaded, provider=provider, candidate_sql=candidate_sql)
    prompt = (
        f"{_reviewer_prompt(loaded, candidate_sql)}\n\n"
        f"## Your previous decision\n\n```json\n{first.model_dump_json(indent=2)}\n```\n\n"
        f"{SELF_REVIEW_INSTRUCTION}"
    )
    return invoke_agent(
        provider=provider,
        model_cls=BaselineDecision,
        agent=REVIEWER_AGENT,
        prompt_version=f"{REVIEWER_PROMPT_VERSION}-self-review",
        system_prompt=REVIEWER_PROMPT.read_text(encoding="utf-8"),
        user_prompt=prompt,
        max_output_tokens=2000,
        seed=loaded.case.seed,
    )
