"""Review one candidate migration, end to end.

    intake -> contract -> authority check -> world plan -> run -> decide
                                                             |
                                              blocked -> remediate -> clean rerun

The agent stage is optional and additive. With ``--no-agents`` the same worlds
run and the same decision comes out; the agents contribute the contract, the
plan, and a correction proposal, and none of them can contribute a verdict.

Remediation happens at most once, on a fresh database, from the original
candidate. The first failure stays in the trace: a bundle showing only the
corrected run would be describing a migration nobody wrote.
"""

from __future__ import annotations

import difflib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from proofbench.agents.contract_analyst import PROMPT_PATH as CONTRACT_ANALYST_PROMPT
from proofbench.agents.contract_analyst import run_contract_analyst
from proofbench.agents.remediation_engineer import PROMPT_PATH as REMEDIATION_PROMPT
from proofbench.agents.remediation_engineer import run_remediation_engineer
from proofbench.agents.test_designer import PROMPT_PATH as TEST_DESIGNER_PROMPT
from proofbench.agents.test_designer import WORLD_CATALOG, run_test_designer
from proofbench.certificate.compiler import build_certificate, write_bundle
from proofbench.decision.policy import decide
from proofbench.domain.certificate import CorrectionRecord, MigrationChangeCertificate
from proofbench.domain.contract import MigrationContract, RemediationPlan, WorldPlan
from proofbench.domain.decision import DecisionRecord, ProviderMode, RunKind
from proofbench.domain.evidence import CheckResult, CheckStatus, EvidenceFailure, WorldResult
from proofbench.domain.ruling import CompiledRuling, Ruling, RulingPacket
from proofbench.domain.trace import EventType
from proofbench.errors import EvidenceIncompleteError
from proofbench.intake.loader import LoadedCase, load_case
from proofbench.providers.base import ModelProvider
from proofbench.sandbox.postgres import MIGRATION_ROLE, FixturePaths, PostgresSandbox
from proofbench.tools.router import ToolRouter
from proofbench.tracing.compiler import compile_trajectory, render_markdown
from proofbench.tracing.hashes import canonical_json, hash_file
from proofbench.tracing.writer import TraceWriter
from proofbench.workflow.agents import IMPLEMENTED_WORLDS, build_router, fake_provider_for
from proofbench.workflow.authority import (
    build_packet,
    compile_ruling,
    has_unresolved_authority,
)
from proofbench.worlds.runner import (
    prepare_world_database,
    run_required_worlds,
    run_visible_tests,
    snapshot_audit,
    snapshot_disbursements,
    snapshot_payments,
)


def fixture_paths(loaded: LoadedCase) -> FixturePaths:
    case = loaded.case
    root = loaded.benchmark_root
    return FixturePaths(
        schema=tuple(root / path for path in case.fixture.schema_paths),
        roles=root / case.fixture.roles_path,
        policies=root / case.fixture.policies_path,
        fixtures=root / case.fixture.fixtures_path,
    )


def new_run_id() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"


def review_case(
    case_path: Path,
    *,
    runs_root: Path,
    run_id: str | None = None,
    provider: ModelProvider | None = None,
    use_agents: bool = True,
    remediation_attempts: int = 1,
    ruling: Ruling | None = None,
) -> tuple[MigrationChangeCertificate, Path]:
    """Run a case and write its complete bundle. Returns the certificate."""
    loaded = load_case(case_path)
    run_id = run_id or new_run_id()
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    if use_agents and provider is None:
        provider = fake_provider_for(case_path.parent)
    # The mode is a fact about how calls were served, recorded once here so the
    # certificate, run.json, and metrics cannot disagree about it again.
    provider_mode = (
        provider.mode if use_agents and provider is not None else ProviderMode.NONE.value
    )

    sandbox = PostgresSandbox(run_id, fixture_paths(loaded))
    writer = TraceWriter(run_dir / "trajectory.jsonl", run_id)
    router = build_router(
        benchmark_root=loaded.benchmark_root, run_dir=run_dir, world_catalog=WORLD_CATALOG
    )

    world_results: list[WorldResult] = []
    visible: list[CheckResult] = []
    failures: list[EvidenceFailure] = []
    resolved_image: str | None = None
    contract: MigrationContract | None = None
    plan: WorldPlan | None = None
    packet: RulingPacket | None = None
    compiled: CompiledRuling | None = None
    authority_questions: list[str] = []
    remediation: RemediationPlan | None = None
    remediation_results: list[WorldResult] = []

    try:
        writer.emit(
            EventType.RUN_STARTED,
            actor="proofbench",
            stage="ingest",
            summary=f"reviewing {loaded.case.case_id}: {loaded.case.title}",
            payload={"inputs_digest": loaded.inputs_digest, "case_id": loaded.case.case_id},
        )
        if use_agents and provider is not None:
            contract = run_contract_analyst(
                provider=provider, router=router, loaded=loaded, trace=writer
            )
            _record_assumptions(writer, contract)
            plan = run_test_designer(
                provider=provider,
                router=router,
                loaded=loaded,
                contract=contract,
                implemented=IMPLEMENTED_WORLDS,
                trace=writer,
            )
            writer.emit(
                EventType.STATE_ENTERED,
                actor="proofbench",
                stage="design-worlds",
                summary=f"plan selects {', '.join(e.world.value for e in plan.entries)}",
                payload={"worlds": [entry.world.value for entry in plan.entries]},
            )

        sandbox.start()
        # Rebind now that credentials exist, so nothing they contain can reach
        # the trace even by accident.
        writer._secrets = sandbox.credentials.secrets()  # noqa: SLF001
        router._secrets = sandbox.credentials.secrets()  # noqa: SLF001
        resolved_image = sandbox.resolved_image

        if contract is not None and ruling is not None:
            compiled = compile_ruling(ruling, contract)
            writer.emit(
                EventType.RULING_RECORDED,
                actor="human",
                stage="authority",
                summary=f"{ruling.reviewer_role} ruled on {ruling.question_id}",
                payload={
                    "ruling_id": ruling.ruling_id,
                    "determination": f"{compiled.column}={compiled.expected_value}",
                    "scope": compiled.predicate,
                },
            )

        # The world databases are cloned before the candidate applies, so the
        # before state is the fixture state rather than whatever the migration
        # left behind.
        base_clone = sandbox.clone("snapshot")
        pre_state = snapshot_payments(sandbox, base_clone)
        pre_audit = snapshot_audit(sandbox, base_clone)
        pre_disbursements = snapshot_disbursements(sandbox, base_clone)

        if contract is not None and has_unresolved_authority(contract, ruling):
            question = contract.unresolved_authority()[0]
            packet = build_packet(
                contract=contract, question=question, sandbox=sandbox, database=base_clone
            )
            authority_questions = [question.question]
            writer.emit(
                EventType.RULING_REQUESTED,
                actor="proofbench",
                stage="authority",
                summary=f"authority required: {question.question}",
                payload={
                    "question_id": question.question_id,
                    "reviewer_qualification": question.reviewer_qualification,
                    "affected_rows": packet.affected_rows.row_count,
                },
            )

        first_world = loaded.case.worlds.required[0].value
        database = prepare_world_database(sandbox, loaded, first_world)
        visible = run_visible_tests(sandbox, database, loaded)
        writer.emit(
            EventType.CHECK_COMPLETED,
            actor="proofbench",
            stage="visible-tests",
            summary=f"{sum(c.status is CheckStatus.PASSED for c in visible)}"
            f"/{len(visible)} visible tests passed",
            payload={"results": [c.status.value for c in visible]},
        )

        if packet is None:
            world_results = run_required_worlds(
                sandbox,
                loaded,
                run_id=run_id,
                trace=writer,
                database_by_world={first_world: database},
                compiled_ruling=compiled,
                pre_state=pre_state,
                pre_audit=pre_audit,
                pre_disbursements=pre_disbursements,
            )
        else:
            # Worlds whose invariants the open question governs would be
            # measuring an assumption rather than a fact, so they do not run.
            writer.emit(
                EventType.STATE_ENTERED,
                actor="proofbench",
                stage="authority",
                summary="worlds deferred pending a domain ruling",
            )

        blocking = any(result.has_blocking_finding() for result in world_results)
        if blocking and remediation_attempts > 0 and use_agents and provider is not None:
            # checks.json must exist before the engineer can read it as evidence.
            (run_dir / "checks.json").write_bytes(
                canonical_json(
                    {"worlds": [result.model_dump(mode="json") for result in world_results]}
                )
            )
            remediation, remediation_results = _attempt_correction(
                provider=provider,
                router=router,
                loaded=loaded,
                contract=contract,
                world_results=world_results,
                sandbox=sandbox,
                run_id=run_id,
                run_dir=run_dir,
                writer=writer,
                attempts=remediation_attempts,
            )
    except EvidenceIncompleteError as exc:
        failures.append(
            EvidenceFailure(
                stage="sandbox",
                reason=exc.message,
                causes=[f"{key}={value}" for key, value in sorted(exc.detail.items())],
            )
        )
        writer.emit(
            EventType.ERROR_RECORDED,
            actor="proofbench",
            stage="sandbox",
            summary=exc.message,
        )
    finally:
        problems = sandbox.stop()
        if problems:
            failures.append(
                EvidenceFailure(stage="cleanup", reason="sandbox cleanup failed", causes=problems)
            )

    # The decision is about the candidate that was submitted. A correction that
    # passes is evidence for its author, not grounds to re-grade the original --
    # and folding it in would let every unsafe candidate reach READY_FOR_REVIEW.
    decision = decide(
        world_results,
        authority_questions=authority_questions,
        evidence_failures=failures,
        contract=contract,
    )
    writer.emit(
        EventType.DECISION_RECORDED,
        actor="decision-policy",
        stage="decide",
        summary=decision.external_state.value,
        payload={
            "state": decision.external_state.value,
            "decisive_check_ids": decision.decisive_check_ids,
        },
    )
    writer.emit(
        EventType.RUN_COMPLETED,
        actor="proofbench",
        stage="complete",
        summary=f"{loaded.case.case_id} -> {decision.external_state.value}",
    )
    writer.close()

    trajectory = compile_trajectory(run_dir / "trajectory.jsonl")
    cert = build_certificate(
        loaded=loaded,
        run_id=run_id,
        run_dir=run_dir,
        decision=decision,
        world_results=world_results,
        visible_tests=visible,
        correction=_correction_record(remediation, remediation_results),
        trajectory=trajectory,
        resolved_image_id=resolved_image,
        run_kind=RunKind.MIGRATION_COURT.value,
        provider_mode=provider_mode,
    )

    write_bundle(
        run_dir=run_dir,
        loaded=loaded,
        cert=cert,
        trajectory_markdown=render_markdown(trajectory, run_id=run_id, case_id=loaded.case.case_id),
        prompt_hashes=_prompt_hashes(contract, plan, remediation),
        extra_artifacts=_artifacts(
            loaded,
            decision,
            world_results,
            remediation_results,
            visible,
            contract,
            plan,
            remediation,
            packet,
            ruling,
            provider_mode=provider_mode,
            model_calls=_count_model_calls(provider),
        ),
    )
    return cert, run_dir


def _count_model_calls(provider: ModelProvider | None) -> int:
    """How many calls actually reached the provider, counted, never assumed.

    Both the fake provider and the metered wrapper expose their call log; a
    bare unmetered provider reports zero, which is the honest floor rather
    than a guess of three.
    """
    calls = getattr(provider, "calls", None)
    return len(calls) if isinstance(calls, list) else 0


def _prompt_hashes(
    contract: MigrationContract | None,
    plan: WorldPlan | None,
    remediation: RemediationPlan | None,
) -> dict[str, str]:
    """Hash the instructions of the agents that actually ran (PRD-FR-001).

    Only agents that produced an artifact appear: a hash for a prompt that never
    reached a model would claim provenance for something that did not happen.
    Empty for a --no-agents run, which is then a true statement.
    """
    hashes: dict[str, str] = {}
    if contract is not None:
        hashes["contract_analyst_v1"] = hash_file(CONTRACT_ANALYST_PROMPT)
    if plan is not None:
        hashes["test_designer_v1"] = hash_file(TEST_DESIGNER_PROMPT)
    if remediation is not None:
        hashes["remediation_engineer_v1"] = hash_file(REMEDIATION_PROMPT)
    return hashes


def _correction_record(
    plan: RemediationPlan | None, results: list[WorldResult]
) -> CorrectionRecord | None:
    """Summarise the correction attempt, if there was one."""
    if plan is None:
        return None
    return CorrectionRecord(
        addresses_invariants=plan.addresses_invariants,
        rationale=plan.rationale,
        regression_check=plan.regression_check,
        # Verified by the rerun, never by the agent's account of it.
        verified=bool(results) and all(not r.has_blocking_finding() for r in results),
        world_results=results,
    )


def _record_assumptions(writer: TraceWriter, contract: MigrationContract) -> None:
    """Put each safety-relevant assumption in the trace before anything runs.

    This is the front half of the narrative a reviewer needs: the assumption the
    agent could not support, then the check that settled it. Recording it only
    afterwards would make the sequence unreconstructable.
    """
    for assumption in contract.assumptions:
        if assumption.safety_relevance.value == "minor":
            continue
        writer.emit(
            EventType.ASSUMPTION_RECORDED,
            actor="contract_analyst",
            stage="contract",
            summary=assumption.statement,
            payload={
                "safety_relevance": assumption.safety_relevance.value,
                "evidence_checked": assumption.evidence_checked,
            },
        )


def _attempt_correction(
    *,
    provider: ModelProvider,
    router: ToolRouter,
    loaded: LoadedCase,
    contract: MigrationContract | None,
    world_results: list[WorldResult],
    sandbox: PostgresSandbox,
    run_id: str,
    run_dir: Path,
    writer: TraceWriter,
    attempts: int = 1,
) -> tuple[RemediationPlan | None, list[WorldResult]]:
    """A configurable, bounded correction loop (PRD-FR-042).

    The bound is the point. A loop that kept proposing until something passed
    would be optimising for a green check rather than a correct migration, so
    the budget is fixed before the first attempt and an exhausted budget
    certifies the blocked result with the best evidence produced so far.
    """
    if contract is None:
        return None, []

    plan: RemediationPlan | None = None
    results: list[WorldResult] = []
    failing = world_results

    for attempt in range(1, attempts + 1):
        try:
            plan_candidate = run_remediation_engineer(
                provider=provider,
                router=router,
                loaded=loaded,
                contract=contract,
                world_results=failing,
                trace=writer,
            )
        except EvidenceIncompleteError as exc:
            # Budget or provider exhausted. The blocked result stands, along
            # with whatever the earlier attempts produced.
            writer.emit(
                EventType.ERROR_RECORDED,
                actor="remediation_engineer",
                stage="remediate",
                summary=f"attempt {attempt}: no correction proposed: {exc.message}",
            )
            break

        plan = plan_candidate
        corrected_path = run_dir / "remediation" / "corrected.sql"
        corrected_path.parent.mkdir(parents=True, exist_ok=True)
        corrected_path.write_text(plan.corrected_sql, encoding="utf-8")

        writer.emit(
            EventType.REMEDIATION_PROPOSED,
            actor="remediation_engineer",
            stage="remediate",
            summary=(
                f"attempt {attempt} of {attempts}: correction addresses "
                f"{', '.join(plan.addresses_invariants)}"
            ),
            payload={"attempt": attempt, "regression_check": plan.regression_check},
        )

        # A clean database from the base fixture. The corrected candidate never
        # sees the state the failed one left behind.
        database = sandbox.clone(f"corrected-{attempt}")
        sandbox.apply_sql_file(database, corrected_path, user=MIGRATION_ROLE)
        results = run_required_worlds(
            sandbox,
            loaded,
            run_id=f"{run_id}-corrected-{attempt}",
            trace=writer,
            database_by_world={loaded.case.worlds.required[0].value: database},
        )
        if not any(result.has_blocking_finding() for result in results):
            break
        failing = results

    return plan, results


def _artifacts(
    loaded: LoadedCase,
    decision: DecisionRecord,
    world_results: list[WorldResult],
    remediation_results: list[WorldResult],
    visible: list[CheckResult],
    contract: MigrationContract | None,
    plan: WorldPlan | None,
    remediation: RemediationPlan | None,
    packet: RulingPacket | None,
    ruling: Ruling | None,
    *,
    provider_mode: str,
    model_calls: int,
) -> dict[str, bytes]:
    """The per-run artifacts PRD section 12 requires, plus the frozen inputs.

    Artifacts that do not apply to this run kind are absent rather than present
    and empty: an empty contract.json would be a claim that no contract was
    produced, which is different from there being no contract stage at all.
    """
    root = loaded.benchmark_root
    not_applicable = [
        name
        for name, produced in (
            ("contract.json", contract is not None),
            ("world-plan.json", plan is not None),
            ("remediation.diff", remediation is not None),
            ("ruling.json", ruling is not None),
        )
        if not produced
    ]
    artifacts: dict[str, bytes] = {
        "run.json": canonical_json(
            {
                "run_kind": "migration_court",
                "provider_mode": provider_mode,
                "case_id": loaded.case.case_id,
                "inputs_digest": loaded.inputs_digest,
                "not_applicable": not_applicable,
            }
        ),
        "checks.json": canonical_json(
            {
                "visible_tests": [check.model_dump(mode="json") for check in visible],
                "worlds": [result.model_dump(mode="json") for result in world_results],
                "worlds_after_correction": [
                    result.model_dump(mode="json") for result in remediation_results
                ],
            }
        ),
        "decision.json": canonical_json(decision.model_dump(mode="json")),
        "metrics.json": canonical_json(
            {
                "worlds_run": len(world_results),
                "checks_executed": sum(len(result.checks) for result in world_results),
                "findings": sum(len(result.findings) for result in world_results),
                "corrected_worlds_run": len(remediation_results),
                "model_calls": model_calls,
            }
        ),
        "inputs/case.yaml": (root / "cases" / loaded.case.case_id / "case.yaml").read_bytes(),
        "inputs/candidate.sql": (root / loaded.case.candidate.migration_path).read_bytes(),
        "inputs/policy.yaml": (root / loaded.case.policy_path).read_bytes(),
    }
    if contract is not None:
        artifacts["contract.json"] = canonical_json(contract.model_dump(mode="json"))
    if plan is not None:
        artifacts["world-plan.json"] = canonical_json(plan.model_dump(mode="json"))
    if remediation is not None:
        artifacts["remediation.json"] = canonical_json(remediation.model_dump(mode="json"))
        # PRD section 12 names remediation.diff. The unified diff is what a
        # reviewer actually reads: the whole point of a minimal correction is
        # visible in how little of it there is.
        original = (root / loaded.case.candidate.migration_path).read_text(encoding="utf-8")
        artifacts["remediation.diff"] = "".join(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                remediation.corrected_sql.splitlines(keepends=True),
                fromfile="candidate.sql",
                tofile="corrected.sql",
            )
        ).encode("utf-8")
    if packet is not None:
        artifacts["ruling-packet.json"] = canonical_json(packet.model_dump(mode="json"))
        artifacts["ruling-packet.md"] = packet.render().encode("utf-8")
    if ruling is not None:
        artifacts["ruling.json"] = canonical_json(ruling.model_dump(mode="json"))
    return artifacts


def load_certificate(path: Path) -> MigrationChangeCertificate:
    return MigrationChangeCertificate.model_validate(json.loads(path.read_text(encoding="utf-8")))
