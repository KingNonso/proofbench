"""Build the run directory: certificate, manifest, bundle root.

Write order is the whole design, because a manifest that hashed the certificate
while the certificate embedded the manifest's hash could never be verified::

    inputs and evidence
      -> certificate.json          (canonical)
      -> certificate.md / .html    (projections of the same record)
      -> manifest.json             (hashes everything above)
      -> bundle-root.txt           (sha256 of manifest.json)

The certificate links the manifest by path and never by digest.
"""

from __future__ import annotations

import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from proofbench.config import POSTGRES_IMAGE, TIMEZONE
from proofbench.domain.certificate import (
    ArtifactHash,
    CorrectionRecord,
    EnvironmentRecord,
    FirstScreen,
    MigrationChangeCertificate,
    RunManifest,
    TrajectorySummary,
)
from proofbench.domain.decision import DecisionRecord
from proofbench.domain.evidence import CheckResult, WorldResult
from proofbench.intake.loader import LoadedCase
from proofbench.tracing.hashes import canonical_json, digest_json, hash_file, sha256_hex

TEMPLATES = Path(__file__).parent / "templates"
EVALUATOR_VERSION = "1.0"

KNOWN_LIMITS = [
    "One world (tenant isolation) is implemented. Money, rolling compatibility, "
    "interruption, rollback, lock budget, and audit history are not yet executed, "
    "so this certificate says nothing about them.",
    "No agent participated in this run. The contract, world selection, and any "
    "remediation are absent by design at this stage, not omitted by failure.",
    "Possible impact is empty because it is derived from contract analysis, which "
    "is not implemented. Only confirmed impact is reported.",
    "ProofBench reviews a candidate in a sandbox. It does not approve, merge, or "
    "apply a migration, and READY_FOR_REVIEW is not an approval.",
]


def _environment(resolved_image_id: str | None) -> EnvironmentRecord:
    return EnvironmentRecord(
        python_version=platform.python_version(),
        platform=platform.platform(),
        postgres_image=POSTGRES_IMAGE,
        resolved_image_id=resolved_image_id,
        timezone=TIMEZONE,
    )


def replay_command(run_dir: Path) -> str:
    return f"uv run proofbench replay {run_dir.as_posix()}/certificate.json"


def build_certificate(
    *,
    loaded: LoadedCase,
    run_id: str,
    run_dir: Path,
    decision: DecisionRecord,
    world_results: list[WorldResult],
    visible_tests: list[CheckResult],
    trajectory: TrajectorySummary,
    correction: CorrectionRecord | None,
    resolved_image_id: str | None,
    run_kind: str,
    provider_mode: str,
) -> MigrationChangeCertificate:
    """Assemble the typed record every output format is rendered from."""
    decisive = _decisive_invariant(decision, world_results)

    return MigrationChangeCertificate(
        run_id=run_id,
        case_id=loaded.case.case_id,
        case_title=loaded.case.title,
        generated_at=datetime.now(UTC),
        run_kind=run_kind,
        provider_mode=provider_mode,
        first_screen=FirstScreen(
            external_state=decision.external_state.value,
            candidate_change=loaded.case.title,
            decisive_invariant=decisive,
            confirmed_blast_radius=list(decision.confirmed),
            required_action=decision.required_action,
            human_ruling=None,
            replay_command=replay_command(run_dir),
        ),
        decision=decision,
        world_results=world_results,
        visible_tests=visible_tests,
        correction=correction,
        trajectory=trajectory,
        environment=_environment(resolved_image_id),
        inputs_digest=loaded.inputs_digest,
        known_limits=KNOWN_LIMITS,
    )


def _decisive_invariant(decision: DecisionRecord, world_results: list[WorldResult]) -> str:
    blocking = [
        finding.invariant_id
        for result in world_results
        for finding in result.findings
        if finding.blocking
    ]
    if blocking:
        return ", ".join(sorted(set(blocking)))
    if not decision.evidence_complete:
        return "none: evidence was incomplete"
    return "none failed"


def render(cert: MigrationChangeCertificate, template_name: str) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    return env.get_template(template_name).render(cert=cert)


def write_bundle(
    *,
    run_dir: Path,
    loaded: LoadedCase,
    cert: MigrationChangeCertificate,
    trajectory_markdown: str,
    extra_artifacts: dict[str, bytes],
) -> RunManifest:
    """Write every artifact in dependency order and return the manifest."""
    run_dir.mkdir(parents=True, exist_ok=True)

    for name, payload in extra_artifacts.items():
        target = run_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)

    (run_dir / "trajectory.md").write_text(trajectory_markdown, encoding="utf-8")

    # 1. canonical JSON, then 2. its projections.
    certificate_bytes = canonical_json(cert.model_dump(mode="json"))
    (run_dir / "certificate.json").write_bytes(certificate_bytes)
    (run_dir / "certificate.md").write_text(render(cert, "certificate.md.j2"), encoding="utf-8")
    (run_dir / "certificate.html").write_text(render(cert, "certificate.html.j2"), encoding="utf-8")

    # 3. the manifest hashes everything written so far, itself excluded.
    artifacts = [
        ArtifactHash(name=path.name, sha256=hash_file(path), bytes=path.stat().st_size)
        for path in sorted(run_dir.rglob("*"))
        if path.is_file() and path.name not in {"manifest.json", "bundle-root.txt", "replay.log"}
    ]
    manifest = RunManifest(
        run_id=cert.run_id,
        case_id=cert.case_id,
        run_kind=cert.run_kind,
        provider_mode=cert.provider_mode,
        created_at=cert.generated_at,
        inputs_digest=loaded.inputs_digest,
        inputs=[
            ArtifactHash(name=item.declared_path, sha256=item.sha256, bytes=item.bytes)
            for item in loaded.inputs
        ],
        artifacts=artifacts,
        policy_hash=next(item.sha256 for item in loaded.inputs if item.field == "policy_path"),
        prompt_hashes={},
        trace_root_hash=cert.trajectory.trace_root_hash,
        world_semantic_digests={
            result.world: result.semantic_digest for result in cert.world_results
        },
        decision_state=cert.decision.external_state.value,
        environment=cert.environment,
        evaluator_version=EVALUATOR_VERSION,
        replay_command=cert.first_screen.replay_command,
    )
    manifest_bytes = canonical_json(manifest.model_dump(mode="json"))
    (run_dir / "manifest.json").write_bytes(manifest_bytes)

    # 4. one line that anchors the whole bundle.
    (run_dir / "bundle-root.txt").write_text(sha256_hex(manifest_bytes) + "\n", encoding="utf-8")
    return manifest


def semantic_digest(cert: MigrationChangeCertificate) -> str:
    return digest_json(cert.semantic_projection(), reject_floats=True)


def python_command() -> str:
    return Path(sys.executable).name
