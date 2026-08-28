"""Cleanup must attempt everything and report what it could not do.

A cleanup failure that replaced the failure which caused it would leave a
reviewer with the symptom and no cause. Needs no Docker daemon: the point is our
collection logic, not Docker's idempotency rules.
"""

from pathlib import Path

import pytest

from proofbench.errors import EvidenceIncompleteError
from proofbench.sandbox import docker, postgres
from proofbench.sandbox.postgres import FixturePaths, PostgresSandbox

FIXTURES = FixturePaths(
    schema=(Path("schema.sql"),),
    roles=Path("roles.sql"),
    policies=Path("policies.sql"),
    fixtures=Path("seed.sql"),
)


def _box():
    return PostgresSandbox("cleanup-probe", FIXTURES)


def test_both_cleanup_steps_are_attempted_and_collected(monkeypatch):
    def boom(_name):
        raise EvidenceIncompleteError("docker command failed")

    monkeypatch.setattr(docker, "stop_and_remove", boom)
    monkeypatch.setattr(docker, "remove_network", boom)

    problems = _box().stop()

    # The network is still attempted after the container failed.
    assert len(problems) == 2
    assert any("container cleanup failed" in problem for problem in problems)
    assert any("network cleanup failed" in problem for problem in problems)


def test_cleanup_failure_raises_when_the_run_itself_succeeded(monkeypatch):
    monkeypatch.setattr(docker, "stop_and_remove", lambda _n: None)
    monkeypatch.setattr(
        docker, "remove_network", lambda _n: (_ for _ in ()).throw(EvidenceIncompleteError("no"))
    )
    monkeypatch.setattr(PostgresSandbox, "start", lambda _self: None)

    with pytest.raises(EvidenceIncompleteError, match="sandbox cleanup failed"), _box():
        pass


def test_cleanup_failure_never_replaces_the_original_failure(monkeypatch):
    monkeypatch.setattr(
        docker,
        "stop_and_remove",
        lambda _n: (_ for _ in ()).throw(EvidenceIncompleteError("container stuck")),
    )
    monkeypatch.setattr(docker, "remove_network", lambda _n: None)
    monkeypatch.setattr(PostgresSandbox, "start", lambda _self: None)

    original = EvidenceIncompleteError("world timed out")
    with pytest.raises(EvidenceIncompleteError) as caught, _box():
        raise original

    # The reportable cause is the world timeout; the leak is kept alongside it.
    assert caught.value is original
    assert "container stuck" in caught.value.detail["cleanup_problems"]


def test_dsn_before_start_is_refused():
    with pytest.raises(EvidenceIncompleteError, match="not started"):
        _box().dsn(postgres.BASE_DATABASE)
