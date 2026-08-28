"""Review one candidate migration, end to end.

A linear sequence, deliberately not a state machine yet: with one world and no
agents there are no branches worth a transition table, and a state machine built
before it has states to hold would be scaffolding rather than structure.

Nothing here calls a model. The decision comes from ``decision.policy``, which is
a pure function over typed evidence.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from proofbench.certificate.compiler import build_certificate, write_bundle
from proofbench.decision.policy import decide
from proofbench.domain.certificate import MigrationChangeCertificate
from proofbench.domain.decision import DecisionRecord, ProviderMode, RunKind
from proofbench.domain.evidence import CheckResult, CheckStatus, EvidenceFailure, WorldResult
from proofbench.domain.trace import EventType
from proofbench.errors import EvidenceIncompleteError
from proofbench.intake.loader import LoadedCase, load_case
from proofbench.sandbox.postgres import FixturePaths, PostgresSandbox
from proofbench.tracing.compiler import compile_trajectory, render_markdown
from proofbench.tracing.hashes import canonical_json
from proofbench.tracing.writer import TraceWriter
from proofbench.worlds.runner import prepare_world_database, run_required_worlds, run_visible_tests


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
) -> tuple[MigrationChangeCertificate, Path]:
    """Run a case and write its complete bundle. Returns the certificate."""
    loaded = load_case(case_path)
    run_id = run_id or new_run_id()
    run_dir = runs_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    sandbox = PostgresSandbox(run_id, fixture_paths(loaded))
    writer = TraceWriter(run_dir / "trajectory.jsonl", run_id)

    world_results: list[WorldResult] = []
    visible: list[CheckResult] = []
    failures: list[EvidenceFailure] = []
    resolved_image: str | None = None

    try:
        writer.emit(
            EventType.RUN_STARTED,
            actor="proofbench",
            stage="ingest",
            summary=f"reviewing {loaded.case.case_id}: {loaded.case.title}",
            payload={"inputs_digest": loaded.inputs_digest, "case_id": loaded.case.case_id},
        )
        sandbox.start()
        # Rebind now that credentials exist, so nothing they contain can reach
        # the trace even by accident.
        writer._secrets = sandbox.credentials.secrets()  # noqa: SLF001
        resolved_image = sandbox.resolved_image

        database = prepare_world_database(sandbox, loaded, "rls")
        visible = run_visible_tests(sandbox, database, loaded)
        writer.emit(
            EventType.CHECK_COMPLETED,
            actor="proofbench",
            stage="visible-tests",
            summary=f"{sum(c.status is CheckStatus.PASSED for c in visible)}"
            f"/{len(visible)} visible tests passed",
            payload={"results": [c.status.value for c in visible]},
        )

        world_results = run_required_worlds(
            sandbox,
            loaded,
            run_id=run_id,
            trace=writer,
            database_by_world={"rls": database},
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

    decision = decide(world_results, evidence_failures=failures)
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
        trajectory=trajectory,
        resolved_image_id=resolved_image,
        run_kind=RunKind.MIGRATION_COURT.value,
        provider_mode=ProviderMode.NONE.value,
    )

    write_bundle(
        run_dir=run_dir,
        loaded=loaded,
        cert=cert,
        trajectory_markdown=render_markdown(trajectory, run_id=run_id, case_id=loaded.case.case_id),
        extra_artifacts=_artifacts(loaded, decision, world_results, visible),
    )
    return cert, run_dir


def _artifacts(
    loaded: LoadedCase,
    decision: DecisionRecord,
    world_results: list[WorldResult],
    visible: list[CheckResult],
) -> dict[str, bytes]:
    """The per-run artifacts PRD section 12 requires, plus the frozen inputs.

    Artifacts that do not apply to this run kind are absent rather than present
    and empty: an empty contract.json would be a claim that no contract was
    produced, which is different from there being no contract stage at all.
    """
    root = loaded.benchmark_root
    return {
        "run.json": canonical_json(
            {
                "run_kind": "migration_court",
                "provider_mode": "none",
                "case_id": loaded.case.case_id,
                "inputs_digest": loaded.inputs_digest,
                "not_applicable": [
                    "contract.json",
                    "world-plan.json",
                    "remediation.diff",
                    "ruling.json",
                ],
            }
        ),
        "checks.json": canonical_json(
            {
                "visible_tests": [check.model_dump(mode="json") for check in visible],
                "worlds": [result.model_dump(mode="json") for result in world_results],
            }
        ),
        "decision.json": canonical_json(decision.model_dump(mode="json")),
        "metrics.json": canonical_json(
            {
                "worlds_run": len(world_results),
                "checks_executed": sum(len(result.checks) for result in world_results),
                "findings": sum(len(result.findings) for result in world_results),
                "model_calls": 0,
            }
        ),
        "inputs/case.yaml": (root / "cases" / loaded.case.case_id / "case.yaml").read_bytes(),
        "inputs/candidate.sql": (root / loaded.case.candidate.migration_path).read_bytes(),
        "inputs/policy.yaml": (root / loaded.case.policy_path).read_bytes(),
    }


def load_certificate(path: Path) -> MigrationChangeCertificate:
    return MigrationChangeCertificate.model_validate(json.loads(path.read_text(encoding="utf-8")))
