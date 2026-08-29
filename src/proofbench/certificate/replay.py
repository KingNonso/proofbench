"""Offline replay.

Re-runs the deterministic evidence behind a certificate and compares what comes
back. It never calls a model — there is nothing in this path that could, which is
what lets the judge command work with no provider key at all.

Verification runs before execution. If the recorded bytes do not match, there is
no point starting a database: the run being replayed is not the run on disk.

Exits non-zero on any mismatch. A replay that reported success while the decision
changed would be worse than no replay, because it would launder a difference into
a confirmation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from proofbench.decision.policy import decide
from proofbench.domain.base import StrictModel
from proofbench.domain.certificate import MigrationChangeCertificate, RunManifest
from proofbench.domain.contract import MigrationContract
from proofbench.domain.ruling import Ruling
from proofbench.errors import CaseValidationError, EvidenceIncompleteError
from proofbench.intake.loader import load_case
from proofbench.sandbox.postgres import PostgresSandbox
from proofbench.tracing.hashes import canonical_json, hash_file, sha256_hex
from proofbench.tracing.validator import validate_trace
from proofbench.workflow.authority import compile_ruling, has_unresolved_authority
from proofbench.workflow.review import fixture_paths, new_run_id
from proofbench.worlds.runner import (
    prepare_world_database,
    run_required_worlds,
    run_visible_tests,
    snapshot_audit,
    snapshot_disbursements,
    snapshot_payments,
)

REPLAY_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class ReplayStep(StrictModel):
    """One verification or comparison, and what it found."""

    name: str
    ok: bool
    detail: str = ""


class ReplayReport(StrictModel):
    """The full outcome. ``ok`` is true only if every step passed."""

    schema_version: Literal["1.0"] = REPLAY_SCHEMA_VERSION
    certificate: str
    run_id: str
    case_id: str
    replayed_at: datetime
    steps: list[ReplayStep] = Field(default_factory=list)
    ok: bool

    def render(self) -> str:
        lines = [
            f"replay {self.case_id} ({self.run_id})",
            f"certificate: {self.certificate}",
            f"replayed_at: {self.replayed_at.isoformat()}",
            "",
        ]
        for step in self.steps:
            mark = "PASS" if step.ok else "FAIL"
            lines.append(f"[{mark}] {step.name}" + (f" — {step.detail}" if step.detail else ""))
        lines += ["", "RESULT: " + ("replay matched" if self.ok else "REPLAY MISMATCH")]
        return "\n".join(lines) + "\n"


def replay(certificate_path: Path, *, benchmark_root: Path) -> ReplayReport:
    """Verify a bundle, re-run its worlds, and compare the outcome."""
    certificate_path = certificate_path.resolve()
    bundle = certificate_path.parent
    steps: list[ReplayStep] = []

    cert = MigrationChangeCertificate.model_validate(
        json.loads(certificate_path.read_text(encoding="utf-8"))
    )
    manifest = RunManifest.model_validate(
        json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    )

    steps.extend(verify_bundle(bundle, manifest))
    steps.extend(_verify_inputs(benchmark_root, manifest))

    if all(step.ok for step in steps):
        steps.extend(_rerun(benchmark_root, cert, manifest, bundle))
    else:
        steps.append(
            ReplayStep(
                name="rerun",
                ok=False,
                detail="skipped: recorded bytes did not verify, so a rerun would compare "
                "against something other than the recorded run",
            )
        )

    report = ReplayReport(
        certificate=certificate_path.name,
        run_id=cert.run_id,
        case_id=cert.case_id,
        replayed_at=datetime.now(UTC),
        steps=steps,
        ok=all(step.ok for step in steps),
    )
    (bundle / "replay.log").write_text(report.render(), encoding="utf-8")
    return report


def verify_bundle(bundle: Path, manifest: RunManifest) -> list[ReplayStep]:
    """Verify recorded bytes only. Starts no database and executes no world."""
    return [*_verify_artifacts(bundle, manifest), _verify_trace(bundle)]


def _verify_artifacts(bundle: Path, manifest: RunManifest) -> list[ReplayStep]:
    steps: list[ReplayStep] = []

    recorded_root = (bundle / "bundle-root.txt").read_text(encoding="utf-8").strip()
    actual_root = sha256_hex(canonical_json(manifest.model_dump(mode="json")))
    steps.append(
        ReplayStep(
            name="bundle root anchors the manifest",
            ok=recorded_root == actual_root,
            detail="" if recorded_root == actual_root else f"{recorded_root} != {actual_root}",
        )
    )

    mismatched: list[str] = []
    missing: list[str] = []
    for artifact in manifest.artifacts:
        candidates = [path for path in bundle.rglob("*") if path.name == artifact.name]
        if not candidates:
            missing.append(artifact.name)
            continue
        if hash_file(candidates[0]) != artifact.sha256:
            mismatched.append(artifact.name)

    steps.append(
        ReplayStep(
            name=f"{len(manifest.artifacts)} artifacts match their recorded digests",
            ok=not mismatched and not missing,
            detail="; ".join(
                filter(
                    None,
                    [
                        f"missing: {', '.join(missing)}" if missing else "",
                        f"changed: {', '.join(mismatched)}" if mismatched else "",
                    ],
                )
            ),
        )
    )
    return steps


def _verify_trace(bundle: Path) -> ReplayStep:
    validation = validate_trace(bundle / "trajectory.jsonl")
    return ReplayStep(
        name="trace chain is intact",
        ok=validation.valid,
        detail="; ".join(validation.problems),
    )


def _verify_inputs(benchmark_root: Path, manifest: RunManifest) -> list[ReplayStep]:
    """The recorded inputs must still be the inputs on disk.

    This is what makes a changed candidate or policy fail replay rather than
    quietly produce a different run that looks equally valid.
    """
    changed: list[str] = []
    absent: list[str] = []
    for item in manifest.inputs:
        path = benchmark_root / item.name
        if not path.is_file():
            absent.append(item.name)
        elif hash_file(path) != item.sha256:
            changed.append(item.name)

    return [
        ReplayStep(
            name=f"{len(manifest.inputs)} declared inputs are unchanged",
            ok=not changed and not absent,
            detail="; ".join(
                filter(
                    None,
                    [
                        f"missing: {', '.join(absent)}" if absent else "",
                        f"changed: {', '.join(changed)}" if changed else "",
                    ],
                )
            ),
        )
    ]


def _rerun(
    benchmark_root: Path, cert: MigrationChangeCertificate, manifest: RunManifest, bundle: Path
) -> list[ReplayStep]:
    """Re-execute what the recorded run executed, and compare.

    Mirrors the recorded run rather than assuming a shape: it re-runs the worlds
    that actually produced results, re-applies the recorded ruling if there was
    one, and re-asks the recorded authority question if the run deferred its
    worlds. A replay that ran a different plan would be comparing two different
    experiments and calling agreement a reproduction.
    """
    case_path = benchmark_root / "cases" / cert.case_id / "case.yaml"
    loaded = load_case(case_path)
    run_id = new_run_id()

    recorded_worlds = [result.world for result in cert.world_results]
    contract = _recorded_contract(bundle)
    ruling = _recorded_ruling(bundle)
    authority = _open_questions(contract, ruling)

    if not recorded_worlds:
        # The recorded run deferred its worlds pending a ruling. Re-executing
        # them now would answer a question the recorded run declined to answer.
        decision = decide([], authority_questions=authority)
        same = decision.external_state.value == manifest.decision_state
        return [
            ReplayStep(
                name="recorded run executed no world; nothing to re-execute",
                ok=True,
                detail=f"open authority questions: {len(authority)}",
            ),
            ReplayStep(
                name="decision matches",
                ok=same,
                detail=""
                if same
                else f"recorded {manifest.decision_state} observed {decision.external_state.value}",
            ),
        ]

    compiled = compile_ruling(ruling, contract) if ruling and contract else None

    sandbox = PostgresSandbox(run_id, fixture_paths(loaded))
    try:
        sandbox.start()
        snapshot_db = sandbox.clone("replay-snapshot")
        pre_state = snapshot_payments(sandbox, snapshot_db)
        pre_audit = snapshot_audit(sandbox, snapshot_db)
        pre_disbursements = snapshot_disbursements(sandbox, snapshot_db)
        database = prepare_world_database(sandbox, loaded, recorded_worlds[0])
        visible = run_visible_tests(sandbox, database, loaded)
        results = run_required_worlds(
            sandbox,
            loaded,
            run_id=run_id,
            database_by_world={recorded_worlds[0]: database},
            compiled_ruling=compiled,
            pre_state=pre_state,
            pre_audit=pre_audit,
            pre_disbursements=pre_disbursements,
        )
    except (EvidenceIncompleteError, CaseValidationError) as exc:
        return [ReplayStep(name="rerun produced evidence", ok=False, detail=exc.message)]
    finally:
        sandbox.stop()

    steps: list[ReplayStep] = []

    observed_digests = {result.world: result.semantic_digest for result in results}
    matched = observed_digests == manifest.world_semantic_digests
    steps.append(
        ReplayStep(
            name="world semantic digests match",
            ok=matched,
            detail=""
            if matched
            else f"recorded {manifest.world_semantic_digests} observed {observed_digests}",
        )
    )

    decision = decide(results, authority_questions=authority)
    same_state = decision.external_state.value == manifest.decision_state
    steps.append(
        ReplayStep(
            name="decision matches",
            ok=same_state,
            detail=""
            if same_state
            else f"recorded {manifest.decision_state} observed {decision.external_state.value}",
        )
    )

    recorded_visible = [check.status.value for check in cert.visible_tests]
    observed_visible = [check.status.value for check in visible]
    steps.append(
        ReplayStep(
            name="visible test outcomes match",
            ok=recorded_visible == observed_visible,
            detail=""
            if recorded_visible == observed_visible
            else f"recorded {recorded_visible} observed {observed_visible}",
        )
    )
    return steps


def _recorded_contract(bundle: Path) -> MigrationContract | None:
    path = bundle / "contract.json"
    if not path.is_file():
        return None
    return MigrationContract.model_validate_json(path.read_text(encoding="utf-8"))


def _recorded_ruling(bundle: Path) -> Ruling | None:
    path = bundle / "ruling.json"
    if not path.is_file():
        return None
    return Ruling.model_validate_json(path.read_text(encoding="utf-8"))


def _open_questions(contract: MigrationContract | None, ruling: Ruling | None) -> list[str]:
    if contract is None or not has_unresolved_authority(contract, ruling):
        return []
    return [question.question for question in contract.unresolved_authority()]
