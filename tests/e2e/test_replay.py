"""Replay is the reproduction claim.

A replay that reported success while something had changed would be worse than
no replay at all: it would launder a difference into a confirmation. So the tests
that matter here are the ones where it must fail.
"""

import json
import shutil

import pytest

from proofbench.certificate.replay import replay
from proofbench.tracing.hashes import canonical_json

pytestmark = [pytest.mark.e2e, pytest.mark.integration]

GOLDEN = "tests/golden/C01"


@pytest.fixture
def golden(repo_root):
    return repo_root / GOLDEN / "certificate.json"


@pytest.fixture
def bench(repo_root):
    return repo_root / "benchmark" / "aidledger"


def test_the_committed_golden_certificate_reproduces(golden, bench, monkeypatch):
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    report = replay(golden, benchmark_root=bench)

    assert report.ok, [step.model_dump() for step in report.steps if not step.ok]
    assert report.case_id == "C01"
    names = [step.name for step in report.steps]
    assert any("world semantic digests match" in name for name in names)
    assert any("decision matches" in name for name in names)


def test_replay_writes_a_log_next_to_the_certificate(golden, bench):
    replay(golden, benchmark_root=bench)
    log = golden.parent / "replay.log"
    assert log.is_file()
    assert "RESULT: replay matched" in log.read_text()


def test_a_changed_candidate_fails_replay(golden, bench, tmp_path):
    # The whole point of freezing input hashes: a different candidate is a
    # different run, not the same run with new output.
    working = tmp_path / "aidledger"
    shutil.copytree(bench, working, symlinks=True)
    candidate = working / "cases" / "C01" / "candidate.sql"
    candidate.write_text(candidate.read_text() + "\n-- tampered\n")

    report = replay(golden, benchmark_root=working)

    assert not report.ok
    failed = [step for step in report.steps if not step.ok]
    assert any("declared inputs are unchanged" in step.name for step in failed)
    # A rerun against unverified bytes would compare against the wrong run.
    assert any(step.name == "rerun" and "skipped" in step.detail for step in failed)


def test_a_changed_policy_fails_replay(golden, bench, tmp_path):
    working = tmp_path / "aidledger"
    shutil.copytree(bench, working, symlinks=True)
    policy = working / "policies" / "base-policy.yaml"
    policy.write_text(policy.read_text().replace("budget_ms: 250", "budget_ms: 500"))

    assert not replay(golden, benchmark_root=working).ok


def test_a_tampered_artifact_fails_replay(golden, bench, tmp_path):
    bundle = tmp_path / "C01"
    shutil.copytree(golden.parent, bundle)
    decision = bundle / "decision.json"
    payload = json.loads(decision.read_text())
    payload["external_state"] = "READY_FOR_REVIEW"
    decision.write_bytes(canonical_json(payload))

    report = replay(bundle / "certificate.json", benchmark_root=bench)

    assert not report.ok
    assert any("artifacts match their recorded digests" in s.name for s in report.steps if not s.ok)


def test_a_tampered_trace_fails_replay(golden, bench, tmp_path):
    bundle = tmp_path / "C01"
    shutil.copytree(golden.parent, bundle)
    trace = bundle / "trajectory.jsonl"
    lines = trace.read_text().splitlines()
    event = json.loads(lines[0])
    event["summary"] = "rewritten history"
    lines[0] = json.dumps(event, sort_keys=True, separators=(",", ":"))
    trace.write_text("\n".join(lines) + "\n")

    report = replay(bundle / "certificate.json", benchmark_root=bench)

    assert not report.ok


def test_a_broken_bundle_root_fails_replay(golden, bench, tmp_path):
    bundle = tmp_path / "C01"
    shutil.copytree(golden.parent, bundle)
    (bundle / "bundle-root.txt").write_text("0" * 64 + "\n")

    report = replay(bundle / "certificate.json", benchmark_root=bench)

    assert not report.ok
    assert any("bundle root" in step.name for step in report.steps if not step.ok)
