"""The certificate is the artifact a reviewer actually reads.

The property that matters most is that JSON, Markdown, and HTML cannot disagree
about the decision: they are projections of one record, and a document whose only
job is to say what happened must not say three things.
"""

import json

import pytest

from proofbench.certificate.compiler import (
    build_certificate,
    render,
    semantic_digest,
    write_bundle,
)
from proofbench.decision.policy import decide
from proofbench.domain.certificate import MigrationChangeCertificate, RunManifest
from proofbench.domain.trace import EventType
from proofbench.tracing.compiler import compile_trajectory, render_markdown
from proofbench.tracing.hashes import canonical_json, sha256_hex
from proofbench.tracing.writer import TraceWriter
from tests.unit import factories


@pytest.fixture
def bundle(tmp_path, c01_case):
    from proofbench.intake.loader import load_case

    loaded = load_case(c01_case)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    writer = TraceWriter(run_dir / "trajectory.jsonl", "unit-run")
    writer.emit(EventType.RUN_STARTED, actor="test", stage="ingest", summary="start")
    writer.emit(EventType.DECISION_RECORDED, actor="decision", stage="decide", summary="BLOCKED")
    writer.emit(EventType.RUN_COMPLETED, actor="test", stage="complete", summary="end")
    writer.close()

    results = [factories.blocked_world()]
    decision = decide(results)
    trajectory = compile_trajectory(run_dir / "trajectory.jsonl")
    cert = build_certificate(
        loaded=loaded,
        run_id="unit-run",
        run_dir=run_dir,
        decision=decision,
        world_results=results,
        visible_tests=[factories.check(status=factories.CheckStatus.PASSED)],
        trajectory=trajectory,
        correction=None,
        resolved_image_id="sha256:abc",
        run_kind="migration_court",
        provider_mode="none",
    )
    manifest = write_bundle(
        run_dir=run_dir,
        loaded=loaded,
        cert=cert,
        trajectory_markdown=render_markdown(trajectory, run_id="unit-run", case_id="C01"),
        extra_artifacts={"decision.json": canonical_json(decision.model_dump(mode="json"))},
    )
    return run_dir, cert, manifest


def test_first_screen_carries_all_seven_prd_fields(bundle):
    _, cert, _ = bundle
    screen = cert.first_screen
    assert screen.external_state == "BLOCKED"
    assert screen.candidate_change
    assert screen.decisive_invariant == "INV-RLS-001"
    assert screen.confirmed_blast_radius
    assert screen.required_action
    assert screen.human_ruling is None  # explicitly absent, not omitted
    assert screen.replay_command.startswith("uv run proofbench replay")


def test_all_three_formats_agree_on_the_decision(bundle):
    run_dir, cert, _ = bundle
    payload = json.loads((run_dir / "certificate.json").read_text())
    markdown = (run_dir / "certificate.md").read_text()
    html = (run_dir / "certificate.html").read_text()

    assert payload["first_screen"]["external_state"] == "BLOCKED"
    assert "BLOCKED" in markdown
    assert "BLOCKED" in html
    for text in (markdown, html):
        assert "INV-RLS-001" in text


def test_html_pulls_no_remote_asset(bundle):
    _, cert, _ = bundle
    html = render(cert, "certificate.html.j2")
    # A certificate that needed the network to render would be unreadable in
    # exactly the offline setting it is meant for.
    for scheme in ("http://", "https://", "//fonts.", "cdn."):
        assert scheme not in html


def test_replay_command_is_visible_in_the_first_screen_of_the_html(bundle):
    _, cert, _ = bundle
    html = render(cert, "certificate.html.j2")
    first_screen = html.split("<h2>")[0]
    assert cert.first_screen.replay_command in first_screen
    assert "confirmed blast radius" in first_screen.lower()


def test_manifest_hashes_the_certificate_but_the_certificate_does_not_hash_the_manifest(bundle):
    run_dir, cert, manifest = bundle
    names = {artifact.name for artifact in manifest.artifacts}
    assert {"certificate.json", "certificate.md", "certificate.html"} <= names
    # No cycle: the certificate links the manifest by path only.
    assert cert.manifest_path == "manifest.json"
    assert manifest.model_dump_json().count(cert.model_dump_json()) == 0


def test_bundle_root_anchors_the_manifest(bundle):
    run_dir, _, manifest = bundle
    recorded = (run_dir / "bundle-root.txt").read_text().strip()
    assert recorded == sha256_hex(canonical_json(manifest.model_dump(mode="json")))


def test_manifest_excludes_itself_and_the_replay_log(bundle):
    _, _, manifest = bundle
    names = {artifact.name for artifact in manifest.artifacts}
    assert "manifest.json" not in names
    assert "bundle-root.txt" not in names
    assert "replay.log" not in names


def test_semantic_digest_ignores_generation_time(bundle):
    _, cert, _ = bundle
    later = cert.model_copy(update={"run_id": "another-run"})
    assert semantic_digest(cert) == semantic_digest(later)


def test_semantic_digest_changes_with_the_decision(bundle):
    _, cert, _ = bundle
    ready = cert.model_copy(update={"decision": decide([factories.world_result()])})
    assert semantic_digest(cert) != semantic_digest(ready)


def test_known_limits_are_stated_rather_than_implied(bundle):
    _, cert, _ = bundle
    joined = " ".join(cert.known_limits).lower()
    assert "not yet executed" in joined
    assert "no agent participated" in joined
    assert "not an approval" in joined


def test_certificate_round_trips_through_canonical_json(bundle):
    run_dir, cert, _ = bundle
    reloaded = MigrationChangeCertificate.model_validate(
        json.loads((run_dir / "certificate.json").read_text())
    )
    assert reloaded.semantic_projection() == cert.semantic_projection()


def test_manifest_round_trips(bundle):
    run_dir, _, manifest = bundle
    reloaded = RunManifest.model_validate(json.loads((run_dir / "manifest.json").read_text()))
    assert reloaded.decision_state == manifest.decision_state
